"""**Der Prozess: Freigabe, Schritt bestätigen, Zustand ableiten.**

Die eine Stelle, an der Einzelinstanzen ihren Status wechseln. Jeder Wechsel schreibt
im selben Atemzug einen Eintrag in den Ereignis-Log (Ebene 3) und zieht die Projektionen
nach (Ebene 2) — es gibt keinen zweiten Schreibweg, und darum können die beiden nicht
auseinanderlaufen.

Gelesen wird PROCESS_CORE.md; hier steht nur, was daraus folgt.
"""

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, insert, update
from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from ..models import (
    Article, Instance, InstanceUnit, Order, OrderLine, OrderUnit, ProcessEvent,
    ProcessStep,
)
from ..models.order_line import LAGER, NEU, ORIGINS
from ..models.process_event import KIND_END, KIND_START, KIND_STEP
from . import article_process, capture as capture_svc, materialize
from .instances import unit_number

#: Wie viele Werte höchstens in eine ``IN``-Liste kommen. Bei 5000 Stück wäre eine
#: einzige Liste ein Abfrage-Text von hunderten Kilobyte; das ist kein Fehler, aber
#: unnötig – und die Grenze kostet nichts.
_CHUNK = 1000


def _chunks(values: list[int]) -> Iterable[list[int]]:
    for i in range(0, len(values), _CHUNK):
        yield values[i:i + _CHUNK]


# ---------------------------------------------------------------------------
# Der Ereignis-Log — die EINE Schreibstelle für einen Statuswechsel
# ---------------------------------------------------------------------------

def _pass(
    db: Session,
    *,
    order: Order,
    units: list[InstanceUnit],
    membership_ids: list[int],
    kind: str,
    step: Optional[ProcessStep],
    status_after: str,
    next_step_id: Optional[int],
    actor_id: Optional[int],
    payloads: Optional[dict[int, dict[str, Any]]] = None,
) -> int:
    """Stücke passieren ein Prozessobjekt.

    Log **und** Projektionen in einem Aufruf. Getrennt wären es zwei Schreibwege, und
    der Wächter «Projektion == Replay(Log)» wäre eine Hoffnung statt einer Folge.

    Die Funktion arbeitet auf einer **Liste**, nicht auf einem Stück: bei 5000 Stück
    wären 15 000 einzelne Anweisungen der Grund, warum «flüssig» nicht mehr stimmt. Ein
    zweiter, schneller Pfad daneben wäre genau der zweite Schreibweg, den es nicht geben
    darf – also ist die Menge hier der Normalfall und das einzelne Stück ihr Sonderfall.
    """
    if not units:
        return 0

    # Der Vorher-Status wird gelesen, **bevor** geschrieben wird – sonst stünde im Log
    # zweimal derselbe Wert und der Übergang wäre nicht mehr ablesbar.
    db.execute(
        insert(ProcessEvent),
        [
            {
                "order_id": order.id,
                "step_id": step.id if step else None,
                "instance_unit_id": u.id,
                "kind": kind,
                "status_before": u.status,
                "status_after": status_after,
                # Was das Modul dabei festgehalten hat – bei der Datenerfassung die
                # ``captures``-Zeile dieses Stücks. Der Log verweist darauf, statt die
                # Werte ein zweites Mal zu führen: zwei Kopien laufen auseinander.
                "payload": (payloads or {}).get(u.id),
                "actor_id": actor_id,
            }
            for u in units
        ],
    )

    unit_ids = [u.id for u in units]
    for part in _chunks(unit_ids):
        db.execute(
            update(InstanceUnit)
            .where(InstanceUnit.id.in_(part))
            .values(status=status_after)
            .execution_options(synchronize_session=False)
        )
    # Am Ende angekommen: das Stück verlässt den Auftrag und ist wieder frei. Genau hier
    # fällt die Exklusivität weg – der partielle Unique-Index greift ab jetzt nicht mehr.
    released = None if next_step_id is not None else datetime.now(timezone.utc)
    for part in _chunks(membership_ids):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(current_step_id=next_step_id, released_at=released)
            .execution_options(synchronize_session=False)
        )
    for u in units:
        u.status = status_after
    return len(units)


# ---------------------------------------------------------------------------
# Die Definitionszeilen
# ---------------------------------------------------------------------------

class _Line:
    """Eine aufgelöste Definitionszeile – Artikel statt Objektnummer, geprüft."""

    def __init__(self, position: int, article: Article, quantity: int, origin: str,
                 unit_numbers: list[str]):
        self.position = position
        self.article = article
        self.quantity = quantity
        self.origin = origin
        self.unit_numbers = unit_numbers
        self.units: list[InstanceUnit] = []

    @property
    def label(self) -> str:
        return f"Zeile {self.position} ({self.article.name})"


def resolve_lines(db: Session, raw: list[dict[str, Any]]) -> list[_Line]:
    """Rohe Definitionszeilen prüfen und auflösen. Jeder Verstoss ist ein harter Fehler."""
    out: list[_Line] = []
    for position, row in enumerate(raw, start=1):
        origin = row.get("origin")
        if origin not in ORIGINS:
            raise HTTPException(
                status_code=400,
                detail=f"Zeile {position}: «{origin}» ist keine Herkunft. Erlaubt: {', '.join(ORIGINS)}.",
            )
        object_id = row.get("article_object_id")
        article = (
            db.query(Article).filter(Article.object_id == object_id).first()
            if object_id else None
        )
        if article is None or not article.is_active:
            raise HTTPException(
                status_code=404, detail=f"Zeile {position}: Artikel {object_id} gibt es nicht.",
            )
        quantity = int(row.get("quantity") or 0)
        if quantity < 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Zeile {position} ({article.name}): die Menge muss mindestens 1 sein. "
                    f"Eine Zeile ohne Stück bewegt nichts."
                ),
            )
        out.append(_Line(
            position=position,
            article=article,
            quantity=quantity,
            origin=origin,
            unit_numbers=[str(n) for n in (row.get("unit_numbers") or [])],
        ))
    return out


def _shape(steps: list[dict[str, Any]]) -> str:
    """Die vergleichbare Form einer Vorlage – **inklusive Konfiguration**.

    Zwei Vorlagen mit gleichen Modultypen, aber verschiedenen Erfassungspunkten sind
    nicht dieselbe Vorlage. Ohne die Konfiguration im Vergleich gälten sie als gleich,
    und der Auftrag führe stillschweigend die eine von beiden.
    """
    import json as _json

    return _json.dumps(
        [[s["module_type"], s["status_before"], s["status_after"], s.get("config")]
         for s in steps],
        sort_keys=True, ensure_ascii=False,
    )


def _from_module(data: dict[str, Any]) -> dict[str, Any]:
    """Eine Modul-Definition aus dem Entwurf in ihre gespeicherte Form bringen.

    **Der Übergang wird abgeleitet, nicht übernommen**: er gehört zum Modultyp
    (``domain/modules``). Was der Entwurf schickt, ist Typ und Konfiguration – und die
    läuft durch die Prüfung des Moduls, nicht durch eine Kopie davon.
    """
    module = modules.get(data.get("module_type"))
    return {
        "module_type": module.key,
        "status_before": module.status_before,
        "status_after": module.status_after,
        "config": module.clean_config(data.get("config")),
    }


def steps_for(db: Session, lines: list[_Line], submitted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Welcher Prozess gilt für diesen Auftrag?

    - Enthält er eine ``Neu``-Zeile, ist es die **Vorlage des Artikels**, als Kopie mit
      Versionsstempel. Sie ist nicht verhandelbar: neue Stücke entstehen genau so, wie
      der Artikel es sagt, sonst wäre der Stempel eine Behauptung.
    - Sonst (reiner ``Lager``-Auftrag) ist es der im Entwurf modellierte Prozess.

    Bringen zwei ``Neu``-Zeilen **verschiedene** Vorlagen mit, ist das ein harter Fehler:
    ein Auftrag hat einen Prozess. Welcher der beiden gälte, kann das System nicht
    entscheiden, und raten wäre hier besonders teuer.
    """
    new_lines = [ln for ln in lines if ln.origin == NEU]
    if not new_lines:
        return [_from_module(s) for s in submitted]

    variants: list[tuple[list[dict[str, Any]], _Line]] = []
    for ln in new_lines:
        copied = article_process.mirror(db, ln.article)
        if not copied:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{ln.label}: dieser Artikel hat keinen Erzeugungsprozess. "
                    f"«Neu» ist erst wählbar, wenn im Artikel-Reiter «Erzeugungsprozess» "
                    f"mindestens ein Modul steht."
                ),
            )
        shape = _shape(copied)
        if variants and shape != _shape(variants[0][0]):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{variants[0][1].label} und {ln.label} bringen verschiedene "
                    f"Erzeugungsprozesse mit – ein Auftrag hat einen Prozess. Lege für "
                    f"den zweiten Artikel einen eigenen Auftrag an."
                ),
            )
        if not variants:
            variants.append((copied, ln))
    return variants[0][0]


# ---------------------------------------------------------------------------
# Freigabe
# ---------------------------------------------------------------------------

def assert_releasable(total_units: int, steps: list[dict[str, Any]]) -> list[str]:
    """Die beiden harten Freigabebedingungen (§6.2) — als Liste dessen, was **fehlt**.

    Namen statt True/False, damit die Oberfläche sagen kann *was* fehlt, statt den
    Nutzer suchen zu lassen. Dieselbe Funktion beantwortet ``/validate`` und schützt
    die Anlage: eine deaktivierte Schaltfläche ist keine Absicherung, sondern eine Bitte.
    """
    missing: list[str] = []
    if total_units < 1:
        missing.append("mindestens eine Einzelinstanz")
    if not steps:
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def _resolve_units(db: Session, numbers: list[str], *, seen: set[str]) -> list[tuple[InstanceUnit, str]]:
    """Nummern → Einzelinstanzen. Unbekannt oder doppelt = harter Fehler, kein Filtern."""
    from .instances import find_unit

    out: list[tuple[InstanceUnit, str]] = []
    for raw in numbers:
        number = (raw or "").strip()
        if number in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Einzelinstanz {number} ist doppelt in der Definition.",
            )
        seen.add(number)
        unit = find_unit(db, number)
        if unit is None or not unit.is_active:
            raise HTTPException(
                status_code=404, detail=f"Einzelinstanz {number} gibt es nicht.",
            )
        out.append((unit, number))
    return out


def _assert_exclusive(db: Session, units: list[tuple[InstanceUnit, str]]) -> None:
    """Exklusivitätsprüfung (§3) — **vor** der Nummernvergabe.

    Der partielle Unique-Index ist die eigentliche Durchsetzung; er hält auch gegen
    zwei gleichzeitige Freigaben. Diese Prüfung davor existiert für die **Meldung**:
    ein Datenbankfehler nennt einen Index, ein Mensch braucht die Objektnummer des
    Auftrags, in dem sein Stück gerade steckt.

    Sie läuft absichtlich, bevor ``object_id_seq`` gezogen wird: eine Sequence ist
    nicht transaktional, ein Rollback danach liesse eine Lücke im Nummernkreis.
    """
    ids = [u.id for u, _ in units]
    if not ids:
        return
    active = (
        db.query(OrderUnit, Order)
        .join(Order, Order.id == OrderUnit.order_id)
        .filter(OrderUnit.instance_unit_id.in_(ids), OrderUnit.released_at.is_(None))
        .all()
    )
    if not active:
        return
    by_unit = {m.instance_unit_id: o for m, o in active}
    clashes = [
        f"{number} (aktiv in Auftrag {by_unit[u.id].object_id})"
        for u, number in units
        if u.id in by_unit
    ]
    raise HTTPException(
        status_code=409,
        detail=(
            "Einzelinstanz ist bereits in einem laufenden Auftrag aktiv: "
            + " · ".join(clashes)
        ),
    )


def _assert_chain(steps: list[dict[str, Any]]) -> None:
    """Die Kette muss schliessen (§4.3) — geprüft **bei der Freigabe**, nicht zur Laufzeit.

    Geprüft wird gegen den **Vorher**-Status des Ende-Objekts (``END_BEFORE``), nicht
    gegen den Endzustand: das Ende ist ein Übergang wie jedes Modul, es *erwartet*
    «Im Prozess» und *setzt* ``order.end_status``. Beides zu verwechseln hiesse, vom
    letzten Modul zu verlangen, dass es den Endzustand selbst schon setzt.

    Das ist der Unterschied zwischen einer Regel und einer Hoffnung: ein Prozess, der
    freigegeben werden konnte, kann nicht mitten drin an einem Statuskonflikt hängen
    bleiben.
    """
    current = st.START_AFTER
    for i, step in enumerate(steps, start=1):
        before = step["status_before"]
        if before != current:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Die Statuskette bricht bei Schritt {i} "
                    f"«{modules.label(step['module_type'])}»: davor "
                    f"steht «{st.label(current)}», das Modul erwartet "
                    f"«{st.label(before)}»."
                ),
            )
        current = step["status_after"]
    if current != st.END_BEFORE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Die Statuskette bricht am Ende: der letzte Schritt endet auf "
                f"«{st.label(current)}», das Ende-Objekt erwartet "
                f"«{st.label(st.END_BEFORE)}»."
            ),
        )


def release(
    db: Session,
    *,
    lines: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    actor_id: Optional[int],
) -> Order:
    """Freigeben = den Prozess starten. **Eine Transaktion**, feste Reihenfolge (§6.3).

    **Jede Prüfung liegt vor der ersten Objektnummer.** Das ist keine Kosmetik: eine
    Sequence ist absichtlich nicht transaktional, ein Rollback danach liesse eine Lücke.
    Ein abgebrochener Freigabe-Versuch verbraucht darum keine Nummer – der einzige
    Ausnahmefall bleibt der echte Parallelzugriff, den erst der Unique-Index abfängt.
    """
    from .objects import next_object_id

    # ── 1. Alles prüfen, was ohne Nummer prüfbar ist ─────────────────────────
    resolved = resolve_lines(db, lines)
    effective = steps_for(db, resolved, steps)

    total = sum(ln.quantity for ln in resolved)
    missing = assert_releasable(total, effective)
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Auftrag ist noch nicht freigebbar – es fehlt: "
                   + ", ".join(missing) + ".",
        )
    for step in effective:
        st.assert_known(step["status_before"], field="Vorher-Status")
        st.assert_known(step["status_after"], field="Nachher-Status")

    end_status = st.DEFAULT_END_STATUS
    _assert_chain(effective)

    # Bestehende Stücke auflösen, Exklusivität und Startzustand prüfen.
    seen: set[str] = set()
    for ln in resolved:
        if ln.origin != LAGER:
            continue
        pairs = _resolve_units(db, ln.unit_numbers, seen=seen)
        _assert_exclusive(db, pairs)
        for unit, number in pairs:
            if unit.status != st.START_BEFORE:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Einzelinstanz {number} steht auf «{st.label(unit.status)}» und "
                        f"kann nicht starten – das Start-Objekt erwartet "
                        f"«{st.label(st.START_BEFORE)}»."
                    ),
                )
        ln.units = [u for u, _ in pairs]

    # Der Plan muss aufgehen, bevor er etwas kostet (§2, harte Invariante).
    planned: list[tuple[int, int, str]] = []
    for ln in resolved:
        if ln.origin == NEU:
            # Rein arithmetisch – prüft die Serialisierung, ohne eine Nummer zu ziehen.
            count, each = materialize.plan(ln.article.serialization, ln.quantity)
            planned.append((ln.quantity, count * each, ln.label))
        else:
            planned.append((ln.quantity, len(ln.units), ln.label))
    materialize.assert_quantity(planned, code=400)

    # ── 2. Ab hier werden Nummern vergeben ───────────────────────────────────
    object_id = next_object_id(db, "order")
    order = Order(
        object_id=object_id,
        # Der Name entsteht im selben Zug wie die Nummer – vorher gibt es keine, und
        # «Ohne Bezeichnung» im Kopf eines laufenden Auftrags ist keine Auskunft.
        name=f"Auftrag {object_id}",
        end_status=end_status,
    )
    db.add(order)
    db.flush()

    for ln in resolved:
        db.add(OrderLine(
            order_id=order.id, position=ln.position, article_id=ln.article.id,
            quantity=ln.quantity, origin=ln.origin,
        ))

    rows: list[ProcessStep] = []
    for position, step in enumerate(effective, start=1):
        row = ProcessStep(
            order_id=order.id,
            position=position,
            module_type=step["module_type"],
            status_before=step["status_before"],
            status_after=step["status_after"],
            config=step.get("config"),
            source_article_id=step.get("source_article_id"),
            source_version=step.get("source_version"),
        )
        db.add(row)
        rows.append(row)
    db.flush()

    # ── 3. Neue Stücke erzeugen – die EINZIGE Stelle, an der das passiert ────
    for ln in resolved:
        if ln.origin == NEU:
            ln.units = materialize.create_for_line(
                db, article=ln.article, quantity=ln.quantity,
            )

    # Und jetzt das Ergebnis gegen dieselbe Invariante halten.
    materialize.assert_quantity(
        [(ln.quantity, len(ln.units), ln.label) for ln in resolved], code=500,
    )

    # ── 4./5. Die Stücke passieren das Start-Objekt, jedes mit eigenem Log-Eintrag ──
    all_units = [u for ln in resolved for u in ln.units]
    db.execute(
        insert(OrderUnit),
        [{"order_id": order.id, "instance_unit_id": u.id} for u in all_units],
    )
    db.flush()
    membership_ids = [
        int(i) for (i,) in db.query(OrderUnit.id).filter(OrderUnit.order_id == order.id).all()
    ]
    _pass(
        db, order=order, units=all_units, membership_ids=membership_ids,
        kind=KIND_START, step=None,
        status_after=st.START_AFTER, next_step_id=rows[0].id, actor_id=actor_id,
    )

    # ── 6. Das erste Modul ist damit aktiv (abgeleitet: dort stehen die Stücke) ──
    return order


# ---------------------------------------------------------------------------
# Schritt bestätigen
# ---------------------------------------------------------------------------

def confirm_step(
    db: Session, *, order: Order, step_id: int, values: dict[str, Any],
    actor_id: Optional[int],
) -> int:
    """«Bestätigen» — der eine Mechanismus, den jedes Modul auslöst.

    Prüft den Vorher-Status, lässt das Modul festhalten was es festhält, setzt den
    Nachher-Status, loggt, rückt vor. Ist der Schritt der letzte, passiert das Stück im
    selben Zug das **Ende-Objekt** und wird frei. Gibt die Zahl der bewegten Stücke zurück.

    **Die Erfassung liegt VOR dem Statuswechsel.** Fehlt ein Pflichtpunkt, ist das ein
    Fehler mit Namen – und es hat sich nichts bewegt. Andersherum stünde die Erfassung
    unter Zugzwang: das Stück wäre schon vorgerückt, und der einzige Weg zurück wäre
    keiner.
    """
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    if order_status(db, order) != st.IM_PROZESS:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Auftrag ist «{st.label(order_status(db, order))}» – "
                    f"es gibt nichts mehr zu bestätigen."),
        )

    waiting = _units_at(db, order, step.id)
    if not waiting:
        raise HTTPException(
            status_code=409,
            detail=(f"Vor «{modules.label(step.module_type)}» steht keine Einzelinstanz – "
                    f"der Schritt ist nicht an der Reihe."),
        )

    following = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.position > step.position)
        .order_by(ProcessStep.position)
        .first()
    )

    for membership, unit in waiting:
        if unit.status != step.status_before:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Einzelinstanz {_number(db, unit)} steht auf "
                    f"«{st.label(unit.status)}», «{modules.label(step.module_type)}» erwartet "
                    f"«{st.label(step.status_before)}»."
                ),
            )

    units = [u for _, u in waiting]
    membership_ids = [m.id for m, _ in waiting]

    # Was das Modul festhält, hängt am **Stück** – ein Wertesatz, eine Zeile je
    # Einzelinstanz (siehe ``capture.record_for_step``).
    captures = capture_svc.record_for_step(
        db, order=order, step=step, units=units, values=values, actor_id=actor_id,
    )
    payloads = {uid: {"capture_id": c.id} for uid, c in captures.items()}

    _pass(
        db, order=order, units=units, membership_ids=membership_ids,
        kind=KIND_STEP, step=step,
        status_after=step.status_after,
        next_step_id=following.id if following else None,
        actor_id=actor_id,
        payloads=payloads,
    )
    if following is None:
        # Das Ende-Objekt im selben Zug: es ist kein Schritt, also ein eigener
        # Eintrag mit ``kind='end'`` – sonst fehlte der Übergang in der Historie.
        _pass(
            db, order=order, units=units, membership_ids=membership_ids,
            kind=KIND_END, step=None,
            status_after=order.end_status, next_step_id=None, actor_id=actor_id,
        )
        db.flush()
    return len(waiting)


# ---------------------------------------------------------------------------
# Ableitungen (Ebene 2 lesen)
# ---------------------------------------------------------------------------

def _units_at(db: Session, order: Order, step_id: Optional[int]):
    return (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(
            OrderUnit.order_id == order.id,
            OrderUnit.released_at.is_(None),
            OrderUnit.current_step_id == step_id,
        )
        .order_by(OrderUnit.id)
        .all()
    )


def _open_memberships(db: Session, order: Order) -> list[OrderUnit]:
    return (
        db.query(OrderUnit)
        .filter(OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None))
        .all()
    )


def _number(db: Session, unit: InstanceUnit) -> str:
    instance = db.query(Instance).filter(Instance.id == unit.instance_id).first()
    if instance is None:
        raise HTTPException(
            status_code=500,
            detail=f"Einzelinstanz {unit.id} hat keine Instanz – der Datenbestand ist kaputt.",
        )
    return unit_number(instance, unit)


def steps_of(db: Session, order: Order) -> list[ProcessStep]:
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id)
        .order_by(ProcessStep.position)
        .all()
    )


def lines_of(db: Session, order: Order) -> list[OrderLine]:
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id)
        .order_by(OrderLine.position)
        .all()
    )


def unit_groups(db: Session, order: Order) -> list[dict[str, Any]]:
    """Wie viele Stücke stehen wo, in welchem Zustand? — **gezählt, nicht aufgelistet**.

    Die Datenhaltung bleibt pro Einzelinstanz; dies ist die Darstellungsfrage. Bei 5000
    Stück ist der Unterschied nicht Geschmack, sondern der zwischen einer Zeile und 5000:
    das Diagramm braucht Zahlen, die einzelnen Nummern holt sich, wer eine Gruppe
    aufklappt (``GET …/units``).
    """
    rows = (
        db.query(
            OrderUnit.current_step_id,
            InstanceUnit.status,
            OrderUnit.released_at.is_(None).label("active"),
            func.count(OrderUnit.id),
        )
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id == order.id)
        .group_by(OrderUnit.current_step_id, InstanceUnit.status, "active")
        .all()
    )
    return [
        {
            "current_step_id": step_id,
            "status": status,
            "active": bool(active),
            "count": int(count),
        }
        for step_id, status, active, count in rows
    ]


def units_page(db: Session, order: Order, *, step_id: Optional[int], active: bool,
               limit: int, offset: int) -> tuple[list[tuple[OrderUnit, InstanceUnit]], int]:
    """Die einzelnen Stücke einer Gruppe – auf Abruf und in Seiten."""
    q = (
        db.query(OrderUnit, InstanceUnit)
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id == order.id)
    )
    q = q.filter(OrderUnit.released_at.is_(None)) if active else q.filter(OrderUnit.released_at.isnot(None))
    q = q.filter(OrderUnit.current_step_id.is_(None) if step_id is None
                 else OrderUnit.current_step_id == step_id)
    total = q.count()
    return q.order_by(OrderUnit.id).limit(limit).offset(offset).all(), total


# ---------------------------------------------------------------------------
# Der Auftragsstatus — ABGELEITET, an genau einer Stelle
# ---------------------------------------------------------------------------
#
# Ein Auftrag hat genau drei Zustände, und keiner davon wird gesetzt: er ergibt sich aus
# dem Zustand seiner Einzelinstanzen. Eine Spalte daneben wäre der zweite Ort — und der
# läuft beim ersten vergessenen Update weg. «Freigegeben» kommt nicht vor: Freigeben ist
# die Aktion, mit der der Auftrag entsteht, kein Zustand, in dem er verweilt.
#
#   Im Prozess      es ist noch etwas unterwegs
#   Abgeschlossen   mindestens ein Stück hat das Ziel erreicht
#   Abgebrochen     nichts kann das Ziel mehr erreichen
#
# Zwei Formen derselben Regel, nebeneinander im selben Modul: ``order_status`` für einen
# geladenen Auftrag, ``order_statuses`` für den Feed (EINE Abfrage, kein N+1).

def _derive(arrived: int, alive: int) -> str:
    """Die Regel selbst — aus zwei Zahlen. Alles andere zählt nur."""
    if arrived:
        return st.ABGESCHLOSSEN
    if alive:
        return st.IM_PROZESS
    # Nichts angekommen und nichts mehr unterwegs: das Ziel ist unerreichbar.
    return st.ABGEBROCHEN


def order_status(db: Session, order: Order) -> str:
    """Der Zustand **eines** Auftrags."""
    return order_statuses(db, [order.id]).get(order.id, st.IM_PROZESS)


def order_statuses(db: Session, order_ids: list[int]) -> dict[int, str]:
    """Der Zustand **vieler** Aufträge – für den Feed, in einer Abfrage.

    «Unterwegs» heisst: die Zugehörigkeit ist offen **und** das Stück gibt es noch. Ein
    deaktiviertes Stück kann nirgends mehr ankommen – ohne diese Bedingung hätte
    «Abgebrochen» keinen Erzeuger und wäre ein Wert, den nie jemand sieht.
    """
    if not order_ids:
        return {}
    rows = (
        db.query(
            OrderUnit.order_id,
            func.count(OrderUnit.id).filter(OrderUnit.released_at.isnot(None)).label("arrived"),
            func.count(OrderUnit.id).filter(
                OrderUnit.released_at.is_(None), InstanceUnit.is_active.is_(True)
            ).label("alive"),
        )
        .join(InstanceUnit, InstanceUnit.id == OrderUnit.instance_unit_id)
        .filter(OrderUnit.order_id.in_(order_ids))
        .group_by(OrderUnit.order_id)
        .all()
    )
    found = {int(oid): _derive(int(a), int(al)) for oid, a, al in rows}
    # Ein Auftrag ohne jede Zugehörigkeit kann es nicht geben (die Freigabe verlangt
    # mindestens eine Einzelinstanz). Käme er doch vor, ist er kein «Im Prozess».
    return {oid: found.get(oid, st.ABGEBROCHEN) for oid in order_ids}


def active_step_id(db: Session, order: Order) -> Optional[int]:
    """Welches Modul ist **jetzt** dran? Das erste, vor dem noch ein Stück steht.

    Abgeleitet, nicht gespeichert: ein zweites Feld dafür wäre eine zweite Wahrheit,
    die beim ersten vergessenen Update auseinanderläuft.
    """
    open_rows = _open_memberships(db, order)
    if not open_rows:
        return None
    waiting = {m.current_step_id for m in open_rows if m.current_step_id is not None}
    for step in steps_of(db, order):
        if step.id in waiting:
            return step.id
    return None


def events_page(db: Session, order: Order, *, limit: int) -> tuple[list[ProcessEvent], int]:
    """Die Historie – die **neuesten** ``limit`` Einträge und wie viele es insgesamt sind.

    Der Deckel wird ausgewiesen, nicht verschwiegen: bei 5000 Stück hat der Log 10 000
    Einträge, und eine Liste, die stumm bei 200 aufhört, sieht aus wie die ganze
    Wahrheit. Die Zahl daneben sagt, dass es mehr gibt.
    """
    total = (
        db.query(func.count(ProcessEvent.id))
        .filter(ProcessEvent.order_id == order.id)
        .scalar() or 0
    )
    rows = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.order_id == order.id)
        .order_by(ProcessEvent.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(rows)), int(total)


def unit_numbers(db: Session, units: Iterable[InstanceUnit]) -> dict[int, str]:
    """Nummern zu Einzelinstanzen — **eine** Abfrage, kein N+1."""
    units = list(units)
    if not units:
        return {}
    instances = {
        i.id: i
        for i in db.query(Instance)
        .filter(Instance.id.in_({u.instance_id for u in units}))
        .all()
    }
    out: dict[int, str] = {}
    for u in units:
        instance = instances.get(u.instance_id)
        if instance is None:
            raise HTTPException(
                status_code=500,
                detail=f"Einzelinstanz {u.id} hat keine Instanz – der Datenbestand ist kaputt.",
            )
        out[u.id] = unit_number(instance, u)
    return out
