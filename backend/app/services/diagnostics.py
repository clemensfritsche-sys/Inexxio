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

**Es muss ohne Vorwissen lesbar sein.** Darum gilt hier durchgehend:

* **Objektnummern statt interner Schlüssel.** Das Journal speichert `orders.id` (296, 297 …);
  am Bildschirm steht die Objektnummer (100000608). Wer die eine nicht in die andere
  übersetzen kann – und das kann niemand –, liest sonst Kauderwelsch.
* **Ein Satz statt eines Tabellen-Abzugs.** «2 Stk an Abweichung 100000610 übergeben» statt
  ``{"table":"instances","field":null,…}``. Die Rohwerte bleiben im Detail (Hover/Bericht).
* **Der Befund zuerst, in Klartext** (``summary``): worum es geht, was passiert ist und
  warum es gerade nicht weitergeht – drei, vier Sätze vor der Chronologie.

**Der Umfang ist die Nachbarschaft des Auftrags**, nicht nur er selbst: seine Unter-Aufträge
und seine Instanzen gehören dazu – dort passieren die Fehler, die man am Auftrag bemerkt.
Jede Zeile nennt darum, zu **welchem Auftrag** sie gehört (``context``).

Rein lesend. Kein eigener Datensatz, keine Objektnummer: eine Diagnose ist eine **Sicht**.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Article, AuditLog, Event, Instance, MaterialMove, Order, UserProfile
from ..models.base import utcnow
from ..schemas.diagnostics import DiagnosticEntry, OrderDiagnostics
from . import ledger, process, shares, subject

# Wie eine Unter-Auftragsart heisst – dieselben Wörter wie in der Oberfläche.
REASON = {"deviation": "Abweichung", "supply": "Nachschub",
          "provisioning": "Bereitstellung", "return": "Retoure"}

# Fachliche Ereignisse in Klartext. Was hier fehlt, erscheint mit seinem technischen
# Namen – das ist ehrlicher als eine erfundene Übersetzung.
EVENT_LABEL = {
    "order.released": "Auftrag freigegeben",
    "order.completed": "Auftrag abgeschlossen",
    "instances.created": "Bestand angelegt",
    "purchase.ordered": "Bestellt",
    "purchase.received": "Ware eingetroffen",
    "inspection.passed": "Datenerfassung bestanden",
    "inspection.failed": "Datenerfassung durchgefallen",
    "movement.recorded": "Bewegung gebucht",
    "scrap.recorded": "Ausgesondert",
    "resource.recorded": "Ressource gebucht",
    "inventory.increased": "Bestand erhöht",
    "inventory.decreased": "Bestand verringert",
    "order.share_taken": "Anteil abgegeben",
    "sale.paid": "Verkauf bezahlt",
    "sale.refunded": "Erstattet",
}

# **Weniger Zeilen, mehr Aussage**: diese Ereignisse sagen dasselbe wie eine
# Journal-Buchung im selben Augenblick – nur ohne Menge und ohne Halter. Zwei Zeilen für
# denselben Vorgang sind keine zweite Information, sie sind Rauschen; die Buchung gewinnt.
MIRRORED_BY_JOURNAL = {"instances.created", "inventory.increased", "inventory.decreased"}

# **Zustände in Worten.** «pending · in_process» ist die Sprache des Datenmodells; im
# Protokoll steht, was es bedeutet – und beantwortet nebenbei die häufigste Rückfrage:
# warum es Bestand gibt, BEVOR die Bestellung eingetroffen ist (weil «in Arbeit» eben
# nicht «am Lager» heisst – gezählt wird erst `passed` + `in_stock`).
QUALITY_LABEL = {"pending": "noch nicht bewertet", "passed": "freigegeben",
                 "blocked": "gesperrt", "failed": "gesperrt"}
DISPOSITION_LABEL = {
    "in_process": "in Arbeit (zählt nicht zum Lagerbestand)", "in_stock": "am Lager",
    "consumed": "verbaut", "sold": "verkauft", "scrapped": "verschrottet",
}

# Was eine Buchung fachlich bedeutet (ADR 007) – als Satzanfang.
MOVE_LABEL = {
    "created": "angelegt", "opening": "Eröffnungsbestand", "taken": "übernommen",
    "returned": "zurückgegeben", "released": "an den Bestand freigegeben",
    "sold": "verkauft", "consumed": "verbaut", "scrapped": "verschrottet",
    "blocked": "gesperrt", "unblocked": "entsperrt",
}


def _num(v: Any) -> Any:
    """`Decimal` ist nicht JSON-fähig – am Rand der Diagnose wird daraus eine Zahl."""
    return float(v) if isinstance(v, Decimal) else v


def _qty(v: Any) -> str:
    """Mengen ohne Nachkomma-Rauschen: «2» statt «2.000» (``Decimal`` behält seinen
    Exponenten – ohne ``normalize`` liest sich jede Stückzahl wie eine Messgrösse)."""
    try:
        d = Decimal(str(v)).normalize()
        return f"{d:f}" if d == d.to_integral_value() else f"{d:f}".rstrip("0")
    except Exception:                                    # pragma: no cover - Defensive
        return str(v)


def _state(quality: Optional[str], disposition: Optional[str], short: bool = False) -> str:
    """«noch nicht bewertet · in Arbeit» statt «pending · in_process» – EINE Übersetzung.
    ``short`` lässt die Erklärung weg (für Schlüssel einer Aufzählung, wo sie sich
    sonst in jeder Zeile wiederholt)."""
    d = DISPOSITION_LABEL.get(disposition or "", disposition or "—")
    if short:
        d = d.split(" (")[0]
    return f"{QUALITY_LABEL.get(quality or '', quality or '—')} · {d}"


class _Names:
    """**Die Übersetzung interner Schlüssel in Objektnummern** – einmal geladen, überall
    benutzt. Ohne sie liest das Protokoll «296 → 297», und niemand weiss, wer das ist."""

    def __init__(self, db: Session, orders: list[Order], insts: list[Instance]):
        self.order_no: dict[int, int] = {o.id: o.object_id for o in orders if o.object_id}
        self.reason: dict[int, str] = {o.id: o.reason or "" for o in orders}
        # Auch Aufträge ausserhalb der Nachbarschaft können in Buchungen auftauchen
        # (ein fremder Auftrag hat sich einen Anteil geholt) – die werden nachgeladen.
        self.db = db
        arts = {i.article_id for i in insts if i.article_id}
        self.article: dict[int, str] = {
            a.id: f"{a.name} {a.object_id}" if a.object_id else a.name
            for a in (db.query(Article).filter(Article.id.in_(arts)).all() if arts else [])}

    def order(self, db_id: Optional[int]) -> str:
        """«Auftrag 100000608» bzw. «Abweichung 100000610»; ``None`` = freier Bestand."""
        if db_id is None:
            return "freier Bestand"
        if db_id not in self.order_no:
            row = self.db.query(Order.object_id, Order.reason).filter(Order.id == db_id).first()
            self.order_no[db_id] = row[0] if row and row[0] else 0
            self.reason[db_id] = (row[1] if row else "") or ""
        no = self.order_no.get(db_id)
        kind = REASON.get(self.reason.get(db_id) or "", "Auftrag")
        return f"{kind} {no}" if no else f"{kind} (intern {db_id})"


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
    """Die abgeleiteten Schritte – Zustand und Fachzeile. Die häufigste Frage bei einem
    hängenden Auftrag lautet «warum ist dieser Schritt nicht dran?»."""
    out: list[dict] = []
    for s in process.build_order_steps(db, order):
        fact = s.get("fact")
        out.append({
            "nr": s["position"], "modul": s["label"], "zustand": s["state"],
            "beleg": getattr(fact, "status", None) or (type(fact).__name__ if fact else None),
            "step_id": s["id"],
        })
    return out


def _instance_rows(db: Session, order: Order, insts: list[Instance], names: _Names) -> list[dict]:
    """Je Instanz: die Projektion (Skalar-Spalten), der **Kontostand** aus dem Journal und
    die Drift-Prüfung. Laufen die beiden auseinander, ist genau das der Bug."""
    rows: list[dict] = []
    for inst in sorted(insts, key=lambda i: i.object_id or 0):
        lots = {f"{names.order(b.holder)} · {_state(b.quality, b.disposition, short=True)}": _num(v)
                for b, v in ledger.lots(db, inst).items()}
        rows.append({
            "instanz": inst.object_id,
            "artikel": names.article.get(inst.article_id, str(inst.article_id)),
            "menge": _num(inst.quantity),
            "zustand": _state(inst.quality, inst.disposition),
            "erzeugt_von": names.order(inst.order_id),
            "festes_subjekt_von": names.order(inst.subject_of_order_id)
                                  if inst.subject_of_order_id else None,
            "ansprüche": {names.order(int(k)): _num(Decimal(str(v)))
                          for k, v in (inst.reservations or {}).items()},
            "gehört_diesem_auftrag": _num(subject.held_quantity(order, inst)),
            "journal_kontostand": lots,
            "drift": ledger.verify_instance(db, inst),
        })
    return rows


def _summary(db: Session, order: Order, subs: list[Order], insts: list[Instance],
             steps: list[dict], shortfall: dict, names: _Names) -> list[str]:
    """**Der Befund in Klartext** – drei, vier Sätze, die die Frage «warum geht es nicht
    weiter?» beantworten, bevor man eine einzige Tabellenzeile liest."""
    out: list[str] = []
    art = names.article.get(order.article_id or 0)
    out.append(
        f"{REASON.get(order.reason or '', 'Auftrag')} {order.object_id} · Status "
        f"«{order.status}»" + (f" · {_qty(order.quantity)} × {art}" if art else ""))
    active = next((s for s in steps if s["zustand"] in ("active", "blocked")), None)
    done = [s for s in steps if s["zustand"] == "done"]
    if steps:
        out.append(
            f"Prozess: {len(done)} von {len(steps)} Schritten erledigt"
            + (f" · steht bei «{active['modul']}» ({active['zustand']})" if active
               else " · alle Schritte durch" if len(done) == len(steps)
               else f" · nichts an der Reihe (Auftrag «{order.status}»)"))
    if shortfall:
        fehlt = " · ".join(f"{_qty(q)} × {names.article.get(a, a)}" for a, q in shortfall.items())
        out.append(f"Es fehlt: {fehlt} → der Prozess ruht, bis darüber entschieden ist "
                   "(ersetzen · Menge reduzieren · warten).")
    for s in subs:
        label = f"{REASON.get(s.reason or '', 'Unter-Auftrag')} {s.object_id}"
        out.append(f"{label}: {s.status} · {_qty(s.quantity)} Stk")
    for inst in insts:
        gone = {b.disposition: v for b, v in ledger.lots(db, inst).items()
                if b.disposition in ledger.TERMINAL}
        if gone:
            weg = " · ".join(f"{_qty(v)} {MOVE_LABEL.get(d, d)}" for d, v in gone.items())
            out.append(f"Instanz {inst.object_id}: {weg} – kommt nicht zurück.")
    drift = [d for i in insts for d in ledger.verify_instance(db, i)]
    if drift:
        out.append("⚠ Journal und Projektion weichen ab: " + " · ".join(drift))
    return out


def _snapshot(db: Session, order: Order, subs: list[Order], insts: list[Instance],
              names: _Names) -> dict:
    """**Der Befund**: der abgeleitete Zustand, aus dem die Oberfläche ihr Bild baut."""
    shortfall = {a: _num(q) for a, q in process.subject_shortfalls(db, order).items()}
    steps = _step_rows(db, order)
    return {
        "zusammenfassung": _summary(db, order, subs, insts, steps, shortfall, names),
        "auftrag": {
            "objektnummer": order.object_id, "status": order.status,
            "art": REASON.get(order.reason or "", "Auftrag"),
            "eltern": order.parent_order_id, "aus_schritt": order.origin_step_id,
            "artikel": names.article.get(order.article_id or 0),
            "menge": _num(order.quantity),
            "freigegeben": order.released_at, "abgeschlossen": order.completed_at,
        },
        "schritte": steps,
        "fehlmenge": {names.article.get(a, str(a)): q for a, q in shortfall.items()},
        "ruht": bool(shortfall),
        "unter_aufträge": [{
            "objektnummer": s.object_id, "art": REASON.get(s.reason or "", "Auftrag"),
            "status": s.status, "aus_schritt": s.origin_step_id, "menge": _num(s.quantity),
        } for s in sorted(subs, key=lambda x: x.object_id or 0)],
        "instanzen": _instance_rows(db, order, insts, names),
    }


def _audit_entry(a: AuditLog, who: Optional[str], ctx: Optional[int]) -> DiagnosticEntry:
    """Eine Feld-Änderung ODER eine Meldung. Zeilen ohne Feld tragen ihre Aussage im
    ``new_value`` – die wurde vorher als «— → Text» gerendert und las sich wie ein Fehler."""
    if a.field_name:
        what = f"{a.table_name}.{a.field_name}"
        text = f"{a.old_value or '—'} → {a.new_value or '—'}"
    else:
        what = a.table_name
        text = a.new_value or "—"
    return DiagnosticEntry(at=a.changed_at_utc, source="audit", kind=what, summary=text,
                           actor=who, object_id=a.object_id, context=ctx,
                           detail={"table": a.table_name, "field": a.field_name,
                                   "old": a.old_value, "new": a.new_value})


def _event_entry(e: Event, who: Optional[str], ctx: Optional[int]) -> DiagnosticEntry:
    # Was hier fehlt, erscheint mit seinem technischen Namen – ehrlicher als eine
    # erfundene Übersetzung.
    label = EVENT_LABEL.get(e.event_type, e.event_type)
    return DiagnosticEntry(at=e.created_at, source="event", kind=e.event_type,
                           summary=str(label), actor=who, object_id=e.object_id,
                           context=ctx, detail=e.payload or {})


def _move_entry(m: MaterialMove, who: Optional[str], names: _Names) -> DiagnosticEntry:
    """**Eine Buchung als Satz** – mit Objektnummern statt interner Schlüssel."""
    verb = MOVE_LABEL.get(m.kind, m.kind)
    qty = _qty(m.quantity)
    if m.kind in ("created", "opening"):
        text = f"{qty} {verb} → {names.order(m.dst_order_id)}"
    elif (m.dst_disposition or "") in ledger.TERMINAL:
        text = f"{qty} {verb} ({names.order(m.dst_order_id)})"
    elif m.src_order_id != m.dst_order_id:
        text = f"{qty} {verb}: {names.order(m.src_order_id)} → {names.order(m.dst_order_id)}"
    else:
        text = f"{qty} {verb} ({names.order(m.dst_order_id)})"
    return DiagnosticEntry(
        at=m.at, source="journal", kind=m.kind, summary=text, actor=who,
        object_id=m.instance_object_id,
        context=names.order_no.get(m.dst_order_id or m.src_order_id or 0) or None,
        detail={"quantity": _num(m.quantity), "note": m.note,
                "src": f"{names.order(m.src_order_id)}/{m.src_disposition or '—'}",
                "dst": f"{names.order(m.dst_order_id)}/{m.dst_disposition or '—'}"})


def _entries(db: Session, order: Order, subs: list[Order], insts: list[Instance],
             names: _Names, limit: int) -> list[DiagnosticEntry]:
    """Die drei Ströme, chronologisch nebeneinander."""
    order_oids = {o.object_id for o in [order, *subs] if o.object_id}
    order_ids = {o.id for o in [order, *subs]}
    inst_oids = {i.object_id for i in insts if i.object_id}
    oids = order_oids | inst_oids
    if not oids:
        return []
    audits = (db.query(AuditLog).filter(AuditLog.object_id.in_(oids))
              .order_by(AuditLog.id.desc()).limit(limit).all())
    events = (db.query(Event).filter(Event.object_id.in_(oids))
              .order_by(Event.id.desc()).limit(limit).all())
    moves = (db.query(MaterialMove).filter(
        (MaterialMove.instance_object_id.in_(inst_oids))
        | (MaterialMove.src_order_id.in_(order_ids))
        | (MaterialMove.dst_order_id.in_(order_ids)))
        .order_by(MaterialMove.id.desc()).limit(limit).all()) if (inst_oids or order_ids) else []

    ids = ({a.user_id for a in audits} | {e.actor_id for e in events}
           | {m.actor_id for m in moves})
    ids = {i for i in ids if i}
    who = ({u.id: u.display_name
            for u in db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()} if ids else {})
    in_scope = lambda oid: oid if oid in order_oids else None      # noqa: E731

    rows = [_audit_entry(a, who.get(a.user_id or 0), in_scope(a.object_id)) for a in audits]
    rows += [_event_entry(e, who.get(e.actor_id or 0), in_scope(e.object_id)) for e in events
             if e.event_type not in MIRRORED_BY_JOURNAL]
    rows += [_move_entry(m, who.get(m.actor_id or 0), names) for m in moves]
    rows.sort(key=lambda r: (r.at is None, r.at))
    return rows


def order_diagnostics(db: Session, order: Order, limit: int = 400) -> OrderDiagnostics:
    """Befund + Protokoll eines Auftrags. ``limit`` je Strom (Deckel gegen Riesen-Antworten;
    was abgeschnitten wurde, sagt ``truncated`` – ein stiller Deckel läse sich wie
    Vollständigkeit)."""
    subs, insts = _scope(db, order)
    names = _Names(db, [order, *subs], insts)
    entries = _entries(db, order, subs, insts, names, limit)
    by_inst = shares.shares_for(db, insts)
    return OrderDiagnostics(
        order_object_id=order.object_id or 0,
        generated_at=utcnow(),
        snapshot=_snapshot(db, order, subs, insts, names),
        # **Wem gehört welche Menge** – dieselbe Aufteilung, die die Auswahl anzeigt.
        # Genau hier stecken die Fehler, die man am Auftrag bemerkt (#390–#394).
        share_map={str(i.object_id): [
            {"auftrag": s.order_object_id, "art": REASON.get(s.reason or "", "Auftrag")
             if s.order_object_id else "frei", "menge": s.quantity}
            for s in by_inst.get(i.id, [])] for i in insts if i.object_id},
        entries=entries,
        truncated=len(entries) >= limit,
    )
