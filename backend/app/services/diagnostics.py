"""**Systemprotokoll eines Auftrags – was hat das System getan, und warum?**

Der Reiter «Verlauf» beantwortet die dritte Frage des Nutzers (*was ist passiert?*) auf
**fachlicher** Ebene: die Material-Buchungen. Für die Fehlersuche reicht das nicht – dort
zählt, **welcher Mechanismus** eine Zahl erzeugt hat, in welcher Reihenfolge, und ob die
abgeleiteten Grössen untereinander noch stimmen.

Genau das liefert dieses Modul, und zwar **ohne eine neue Wahrheit zu erfinden**: es liest
die drei Ströme, die es ohnehin gibt, und stellt sie nebeneinander –

    audit    ``audit_log``       – wer hat welches Feld geändert (Absicht)
    event    ``events``          – welches fachliche Ereignis wurde ausgelöst (Wirkung)
    journal  ``material_moves``  – wo ist das Material hin (Bestand, ADR 007)

dazu einen **Befund** (``snapshot``): der abgeleitete Zustand zum Abfragezeitpunkt – Schritte,
Fehlmenge, Anteile, Kontostand je Instanz und die **Drift-Prüfung** (``ledger.verify_instance``).
Ein Bug zeigt sich fast immer als Widerspruch zwischen zwei dieser Angaben; nebeneinander
gestellt ist er in Sekunden zu sehen statt in einer Stunde Rekonstruktion.

**Der Umfang ist die Nachbarschaft des Auftrags**, nicht nur er selbst: seine Unter-Aufträge
und seine Instanzen gehören dazu – dort passieren die Fehler, die man am Auftrag bemerkt.

Rein lesend. Kein eigener Datensatz, keine Objektnummer: eine Diagnose ist eine **Sicht**.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuditLog, Event, Instance, MaterialMove, Order, UserProfile
from ..models.base import utcnow
from ..schemas.diagnostics import DiagnosticEntry, OrderDiagnostics
from . import ledger, process, shares, subject


def _actors(db: Session, ids: set[int]) -> dict[int, str]:
    """Namen der beteiligten Personen – EINE Abfrage (kein N+1)."""
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u.display_name
            for u in db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()}


def _num(v: Any) -> Any:
    """`Decimal` ist nicht JSON-fähig – am Rand der Diagnose wird daraus eine Zahl."""
    return float(v) if isinstance(v, Decimal) else v


def _scope(db: Session, order: Order) -> tuple[list[Order], list[Instance]]:
    """Die Nachbarschaft: der Auftrag, seine Unter-Aufträge und alle beteiligten Instanzen."""
    subs = (db.query(Order).filter(Order.parent_order_id == order.object_id).all()
            if order.object_id else [])
    seen: dict[int, Instance] = {}
    for o in [order, *subs]:
        for inst in subject.order_instances(db, o):
            if inst.object_id:
                seen[inst.object_id] = inst
    return subs, list(seen.values())


def _step_rows(db: Session, order: Order) -> list[dict]:
    """Die abgeleiteten Schritte – Zustand, Fachzeile, Ursprung. Die häufigste Frage bei
    einem hängenden Auftrag lautet «warum ist dieser Schritt nicht dran?»."""
    out: list[dict] = []
    for s in process.build_order_steps(db, order):
        fact = s.get("fact")
        out.append({
            "step_id": s["id"], "type": s["step_type"], "state": s["state"],
            "position": s["position"],
            "fact": type(fact).__name__ if fact is not None else None,
            "fact_status": getattr(fact, "status", None),
            "fact_done": getattr(fact, "done", None),
            "facts": len(s.get("facts") or []),
        })
    return out


def _instance_rows(db: Session, order: Order, insts: list[Instance]) -> list[dict]:
    """Je Instanz: die Projektion (Skalar-Spalten), der **Kontostand** aus dem Journal und
    die Drift-Prüfung. Laufen die beiden auseinander, ist genau das der Bug."""
    rows: list[dict] = []
    for inst in sorted(insts, key=lambda i: i.object_id or 0):
        lots = {f"{b.holder or 'frei'}·{b.quality}·{b.disposition}": _num(v)
                for b, v in ledger.lots(db, inst).items()}
        rows.append({
            "instance": inst.object_id,
            "article": inst.article_id,
            "quantity": _num(inst.quantity),
            "quality": inst.quality,
            "disposition": inst.disposition,
            "creator_order": inst.order_id,
            "subject_of_order": inst.subject_of_order_id,
            "reservations": {k: _num(Decimal(str(v)))
                             for k, v in (inst.reservations or {}).items()},
            "held_by_this_order": _num(subject.held_quantity(order, inst)),
            "ledger_lots": lots,
            "drift": ledger.verify_instance(db, inst),
        })
    return rows


def _snapshot(db: Session, order: Order, subs: list[Order], insts: list[Instance]) -> dict:
    """**Der Befund**: der abgeleitete Zustand, aus dem die Oberfläche ihr Bild baut."""
    shortfall = {str(a): _num(q) for a, q in process.subject_shortfalls(db, order).items()}
    return {
        "order": {
            "object_id": order.object_id, "status": order.status,
            "reason": order.reason, "parent": order.parent_order_id,
            "origin_step_id": order.origin_step_id, "abort_into": order.abort_into_id,
            "article_id": order.article_id, "quantity": _num(order.quantity),
            "released_at": order.released_at, "completed_at": order.completed_at,
        },
        "steps": _step_rows(db, order),
        "shortfall": shortfall,
        "paused": bool(shortfall),
        "sub_orders": [{
            "object_id": s.object_id, "reason": s.reason, "status": s.status,
            "origin_step_id": s.origin_step_id, "quantity": _num(s.quantity),
        } for s in sorted(subs, key=lambda x: x.object_id or 0)],
        "instances": _instance_rows(db, order, insts),
    }


def _entries(db: Session, order: Order, subs: list[Order], insts: list[Instance],
             limit: int) -> list[DiagnosticEntry]:
    """Die drei Ströme, chronologisch nebeneinander."""
    order_oids = {o.object_id for o in [order, *subs] if o.object_id}
    order_ids = {o.id for o in [order, *subs]}
    inst_oids = {i.object_id for i in insts if i.object_id}
    oids = order_oids | inst_oids
    rows: list[tuple[Any, DiagnosticEntry]] = []
    actor_ids: set[int] = set()

    audits = (db.query(AuditLog).filter(AuditLog.object_id.in_(oids))
              .order_by(AuditLog.id.desc()).limit(limit).all() if oids else [])
    events = (db.query(Event).filter(Event.object_id.in_(oids))
              .order_by(Event.id.desc()).limit(limit).all() if oids else [])
    moves = (db.query(MaterialMove).filter(
        (MaterialMove.instance_object_id.in_(inst_oids))
        | (MaterialMove.src_order_id.in_(order_ids))
        | (MaterialMove.dst_order_id.in_(order_ids)))
        .order_by(MaterialMove.id.desc()).limit(limit).all() if (inst_oids or order_ids) else [])
    actor_ids |= {a.user_id for a in audits if a.user_id}
    actor_ids |= {e.actor_id for e in events if e.actor_id}
    actor_ids |= {m.actor_id for m in moves if m.actor_id}
    names = _actors(db, actor_ids)

    for a in audits:
        rows.append((a.changed_at_utc, DiagnosticEntry(
            at=a.changed_at_utc, source="audit", kind=f"{a.table_name}.{a.field_name or '—'}",
            summary=f"{a.old_value or '—'} → {a.new_value or '—'}",
            actor=names.get(a.user_id or 0), object_id=a.object_id,
            detail={"table": a.table_name, "field": a.field_name,
                    "old": a.old_value, "new": a.new_value})))
    for e in events:
        rows.append((e.created_at, DiagnosticEntry(
            at=e.created_at, source="event", kind=e.event_type,
            summary=e.object_type, actor=names.get(e.actor_id or 0),
            object_id=e.object_id, detail=e.payload or {})))
    for m in moves:
        rows.append((m.at, DiagnosticEntry(
            at=m.at, source="journal", kind=m.kind,
            summary=(f"{_num(m.quantity)} · "
                     f"{m.src_order_id or 'frei'}/{m.src_disposition or '—'}"
                     f" → {m.dst_order_id or 'frei'}/{m.dst_disposition or '—'}"),
            actor=names.get(m.actor_id or 0), object_id=m.instance_object_id,
            detail={"quantity": _num(m.quantity), "note": m.note,
                    "src_order": m.src_order_id, "src_quality": m.src_quality,
                    "src_disposition": m.src_disposition, "dst_order": m.dst_order_id,
                    "dst_quality": m.dst_quality, "dst_disposition": m.dst_disposition})))

    rows.sort(key=lambda r: (r[0] is None, r[0]))
    return [e for _, e in rows]


def order_diagnostics(db: Session, order: Order, limit: int = 400) -> OrderDiagnostics:
    """Befund + Protokoll eines Auftrags. ``limit`` je Strom (Deckel gegen Riesen-Antworten;
    was abgeschnitten wurde, sagt ``truncated`` – ein stiller Deckel läse sich wie
    Vollständigkeit)."""
    subs, insts = _scope(db, order)
    entries = _entries(db, order, subs, insts, limit)
    by_inst = shares.shares_for(db, insts)
    return OrderDiagnostics(
        order_object_id=order.object_id or 0,
        generated_at=utcnow(),
        snapshot=_snapshot(db, order, subs, insts),
        # **Wem gehört welche Menge** – dieselbe Aufteilung, die die Auswahl anzeigt.
        # Genau hier stecken die Fehler, die man am Auftrag bemerkt (#390–#394).
        share_map={str(i.object_id): [
            {"order": s.order_object_id, "reason": s.reason, "quantity": s.quantity}
            for s in by_inst.get(i.id, [])] for i in insts if i.object_id},
        entries=entries,
        truncated=len(entries) >= limit,
    )
