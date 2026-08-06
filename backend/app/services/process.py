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
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import (
    Instance, InstanceUnit, Order, OrderUnit, ProcessEvent, ProcessStep,
)
from ..models.order import COMPLETED, RELEASED
from ..models.process_event import KIND_END, KIND_START, KIND_STEP
from .instances import unit_number


# ---------------------------------------------------------------------------
# Der Ereignis-Log — die EINE Schreibstelle für einen Statuswechsel
# ---------------------------------------------------------------------------

def _pass(
    db: Session,
    *,
    order: Order,
    unit: InstanceUnit,
    membership: OrderUnit,
    kind: str,
    step: Optional[ProcessStep],
    status_after: str,
    next_step_id: Optional[int],
    actor_id: Optional[int],
    payload: Optional[dict[str, Any]] = None,
) -> ProcessEvent:
    """Ein Stück passiert ein Prozessobjekt.

    Log **und** Projektionen in einem Aufruf. Getrennt wären es zwei Schreibwege, und
    der Wächter «Projektion == Replay(Log)» wäre eine Hoffnung statt einer Folge.
    """
    event = ProcessEvent(
        order_id=order.id,
        step_id=step.id if step else None,
        instance_unit_id=unit.id,
        kind=kind,
        status_before=unit.status,
        status_after=status_after,
        payload=payload,
        actor_id=actor_id,
    )
    db.add(event)

    unit.status = status_after
    membership.current_step_id = next_step_id
    if next_step_id is None:
        # Am Ende angekommen: das Stück verlässt den Auftrag und ist wieder frei.
        # Genau hier fällt die Exklusivität weg – der partielle Unique-Index greift
        # ab jetzt nicht mehr auf dieses Stück.
        membership.released_at = datetime.now(timezone.utc)
    return event


# ---------------------------------------------------------------------------
# Freigabe
# ---------------------------------------------------------------------------

def assert_releasable(units: list[str], steps: list[dict[str, Any]]) -> list[str]:
    """Die beiden harten Freigabebedingungen (§6.2) — als Liste dessen, was **fehlt**.

    Namen statt True/False, damit die Oberfläche sagen kann *was* fehlt, statt den
    Nutzer suchen zu lassen. Dieselbe Funktion beantwortet ``/validate`` und schützt
    die Anlage: eine deaktivierte Schaltfläche ist keine Absicherung, sondern eine Bitte.
    """
    missing: list[str] = []
    if not units:
        missing.append("mindestens eine Einzelinstanz")
    if not steps:
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def _resolve_units(db: Session, numbers: list[str]) -> list[tuple[InstanceUnit, str]]:
    """Nummern → Einzelinstanzen. Unbekannt oder doppelt = harter Fehler, kein Filtern."""
    from .instances import find_unit

    seen: set[str] = set()
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


def _assert_chain(steps: list[dict[str, Any]], end_status: str) -> None:
    """Die Kette muss schliessen (§4.3) — geprüft **bei der Freigabe**, nicht zur Laufzeit.

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
                    f"Die Statuskette bricht bei Schritt {i} «{step['name']}»: davor "
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
    unit_numbers: list[str],
    steps: list[dict[str, Any]],
    actor_id: Optional[int],
) -> Order:
    """Freigeben = den Prozess starten. **Eine Transaktion**, feste Reihenfolge (§6.3).

    Die Reihenfolge weicht in einem Punkt bewusst von der Vorgabe ab: die
    Exklusivitätsprüfung läuft **vor** der Nummernvergabe. Grund steht in
    ``_assert_exclusive`` — hinterher geprüft, kostete jeder Verstoss eine Objektnummer.
    """
    from .objects import next_object_id

    # 1 — Freigabebedingungen
    missing = assert_releasable(unit_numbers, steps)
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Auftrag ist noch nicht freigebbar – es fehlt: "
                   + ", ".join(missing) + ".",
        )
    for step in steps:
        st.assert_known(step["status_before"], field="Vorher-Status")
        st.assert_known(step["status_after"], field="Nachher-Status")

    end_status = st.DEFAULT_END_STATUS
    _assert_chain(steps, end_status)

    units = _resolve_units(db, unit_numbers)

    # 2 — Exklusivität (siehe Docstring: vor der Nummer)
    _assert_exclusive(db, units)

    for unit, number in units:
        if unit.status != st.START_BEFORE:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Einzelinstanz {number} steht auf «{st.label(unit.status)}» und "
                    f"kann nicht starten – das Start-Objekt erwartet "
                    f"«{st.label(st.START_BEFORE)}»."
                ),
            )

    # 3 — Datensatz anlegen
    order = Order(
        object_id=next_object_id(db, "order"),
        status=RELEASED,
        end_status=end_status,
    )
    db.add(order)
    db.flush()

    rows: list[ProcessStep] = []
    for position, step in enumerate(steps, start=1):
        row = ProcessStep(
            order_id=order.id,
            position=position,
            module_type=step["module_type"],
            name=step["name"],
            status_before=step["status_before"],
            status_after=step["status_after"],
        )
        db.add(row)
        rows.append(row)
    db.flush()

    first = rows[0]

    # 4+5 — die Stücke passieren das Start-Objekt, jedes mit eigenem Log-Eintrag
    for unit, _ in units:
        membership = OrderUnit(order_id=order.id, instance_unit_id=unit.id)
        db.add(membership)
        db.flush()
        _pass(
            db, order=order, unit=unit, membership=membership,
            kind=KIND_START, step=None,
            status_after=st.START_AFTER, next_step_id=first.id, actor_id=actor_id,
        )

    # 6 — das erste Modul ist damit aktiv (abgeleitet: dort stehen die Stücke)
    return order


# ---------------------------------------------------------------------------
# Schritt bestätigen
# ---------------------------------------------------------------------------

def confirm_step(
    db: Session, *, order: Order, step_id: int, actor_id: Optional[int],
) -> int:
    """«Schritt bestätigen» — der Mechanismus, den das Testmodul auslöst.

    Prüft den Vorher-Status, setzt den Nachher-Status, loggt, rückt vor. Ist der
    Schritt der letzte, passiert das Stück im selben Zug das **Ende-Objekt** und wird
    frei. Gibt die Zahl der bewegten Stücke zurück.
    """
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
    if order.status != RELEASED:
        raise HTTPException(
            status_code=409,
            detail="Der Auftrag ist abgeschlossen – es gibt nichts mehr zu bestätigen.",
        )

    waiting = _units_at(db, order, step.id)
    if not waiting:
        raise HTTPException(
            status_code=409,
            detail=f"Vor «{step.name}» steht keine Einzelinstanz – der Schritt ist nicht an der Reihe.",
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
                    f"«{st.label(unit.status)}», «{step.name}» erwartet "
                    f"«{st.label(step.status_before)}»."
                ),
            )

    for membership, unit in waiting:
        _pass(
            db, order=order, unit=unit, membership=membership,
            kind=KIND_STEP, step=step,
            status_after=step.status_after,
            next_step_id=following.id if following else None,
            actor_id=actor_id,
        )
        if following is None:
            # Das Ende-Objekt im selben Zug: es ist kein Schritt, also ein eigener
            # Eintrag mit ``kind='end'`` – sonst fehlte der Übergang in der Historie.
            _pass(
                db, order=order, unit=unit, membership=membership,
                kind=KIND_END, step=None,
                status_after=order.end_status, next_step_id=None, actor_id=actor_id,
            )

    if following is None:
        db.flush()
        if not _open_memberships(db, order):
            order.status = COMPLETED
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


def events_of(db: Session, order: Order) -> list[ProcessEvent]:
    return (
        db.query(ProcessEvent)
        .filter(ProcessEvent.order_id == order.id)
        .order_by(ProcessEvent.id)
        .all()
    )


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
