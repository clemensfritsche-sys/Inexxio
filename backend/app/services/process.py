"""**Der Prozess zur Laufzeit: Modul bestätigen, weiterziehen, ankommen, zurückkehren.**

Die eine Stelle, an der Einzelinstanzen ihren Status wechseln (``_pass`` – auch die
Freigabe, ``services/release``, schreibt durch sie): Log und Projektionen im selben Zug,
kein zweiter Schreibweg. Die Regeln stehen in PROCESS_CORE.md.
"""

import re
from typing import Any, Iterable, Optional

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from . import log
from ..models import (
    Instance, InstanceUnit, Order, OrderUnit, ProcessStep,
)
from ..models.process_event import (
    KIND_CAPTURE, KIND_END, KIND_RETURN, KIND_START, KIND_STEP,
)
from . import (
    capture as capture_svc,
    consumption as consumption_svc, voucher as voucher_svc,
    places as places_svc, sampling,
)
from .instances import number_of, unit_numbers
from .order_state import (
    _chunks, _latest_captures, _order_number, _units_at, order_status, pending_returns,
    steps_of,
)
from ..domain.errors import Conflict, Failed, Invalid, NotFound
from ..core import clock

#: Wie die Instanz vor der Eingabe verifiziert wurde – Scan oder Tastatur, beides ist eine
#: Bestätigung und steht im Log.
VERIFY_SCAN, VERIFY_MANUAL = "scan", "manual"
VERIFICATIONS = (VERIFY_SCAN, VERIFY_MANUAL)


# ---------------------------------------------------------------------------
# Der Ereignis-Log — die EINE Schreibstelle für einen Statuswechsel
# ---------------------------------------------------------------------------

def _assert_not_terminal(db: Session, units: list[InstanceUnit], status_after: str) -> None:
    """►►► **Ein Endzustand wird nicht überschrieben.** ◄◄◄

    Hier, weil **jeder** Statuswechsel hier durchläuft (§4.1) – ein neues Modul erbt die
    Regel. Darunter liegt derselbe Satz als Trigger (``statuses.terminal_guard_sql``); diese
    Prüfung gibt dem Fehler einen Satz und bricht ab, bevor etwas geschrieben ist.
    """
    stuck = [u for u in units if st.is_terminal(u.status)]
    if not stuck:
        return
    first = stuck[0]
    raise Conflict(f"Einzelinstanz {number_of(db, first)} ist «{st.label(first.status)}» – das ist "
            f"ein Endzustand. Er wird nicht überschrieben"
            + (f" (versucht: «{st.label(status_after)}»)" if status_after else "")
            + (f"; betroffen sind {len(stuck)} Stücke" if len(stuck) > 1 else "")
            + ". Was passiert ist, ist passiert.")


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
    """Stücke passieren ein Prozessobjekt – Log **und** Projektionen in einem Aufruf.

    Arbeitet auf einer **Liste**: die Menge ist der Normalfall, das einzelne Stück ihr
    Sonderfall; ein zweiter, schneller Pfad wäre ein zweiter Schreibweg.
    """
    if not units:
        return 0
    _assert_not_terminal(db, units, status_after)

    # Der Vorher-Status wird gelesen, **bevor** geschrieben wird.
    log.process_events(
        db,
        [
            {
                "order_id": order.id,
                "step_id": step.id if step else None,
                "instance_unit_id": u.id,
                "kind": kind,
                "status_before": u.status,
                "status_after": status_after,
                # Was das Modul festhielt (``captures``-Zeile) – der Log verweist darauf.
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
    # Am Ende angekommen: das Stück verlässt den Auftrag, die Exklusivität fällt weg.
    released = None if next_step_id is not None else clock.utcnow()
    for part in _chunks(membership_ids):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(current_step_id=next_step_id, released_at=released)
            .execution_options(synchronize_session=False)
        )
    for u in units:
        u.status = status_after

    # ►► **Jedes Stück behält seinen Ort – ausser es ist endgültig weg.** ◄◄ Die Regel hängt
    # am Status und steht darum an der EINEN Stelle, an der ein Status geschrieben wird.
    if st.is_terminal(status_after):
        places_svc.forget(db, units)
    return len(units)


def lock_orders(db: Session, order_ids: Iterable[int]) -> None:
    """►►► **Aufträge sperren, bevor an ihnen geschrieben wird** – in fester Reihenfolge. ◄◄◄

    Jeder Schreibweg an einem laufenden Auftrag nimmt zuerst diese Zeilensperre; zwei
    gleichzeitige Vorgänge laufen nacheinander. Sortiert nach ``id`` gegen Verklemmung.
    """
    ids = sorted({int(i) for i in order_ids})
    if ids:
        db.execute(select(Order.id).where(Order.id.in_(ids)).order_by(Order.id)
                   .with_for_update())


def _join(db: Session, rows: list[dict[str, Any]]) -> list[int]:
    """Die Zugehörigkeiten anlegen – **ein Stück in genau einem Auftrag** (§3).

    Ein Verstoss gegen den partiellen Unique-Index wird ein 409 mit der Nummer des Stücks
    (Savepoint hält die Transaktion lesbar).
    """
    try:
        with db.begin_nested():
            db.execute(insert(OrderUnit), rows)
    except IntegrityError as exc:
        found = re.search(r"\(instance_unit_id\)=\((\d+)\)", str(exc.orig))
        unit = db.get(InstanceUnit, int(found.group(1))) if found else None
        name = f"Einzelinstanz {number_of(db, unit)}" if unit else "Eine Einzelinstanz"
        raise Conflict(f"{name} läuft inzwischen in einem anderen Auftrag – die Auswahl ist "
                    f"veraltet. Bitte prüfen und erneut freigeben.") from None
    return [int(i) for (i,) in db.query(OrderUnit.id).filter(
        OrderUnit.order_id == rows[0]["order_id"],
        OrderUnit.instance_unit_id.in_([r["instance_unit_id"] for r in rows]),
        OrderUnit.released_at.is_(None),
    ).all()]


def _enter_at_step(db: Session, *, order: Order, step: ProcessStep,
                   units: list[InstanceUnit], actor_id: Optional[int]) -> list[int]:
    """►►► **Der zweite Eintrittspunkt: ein Stück tritt an einem MODUL in den Auftrag.** ◄◄◄

    Für ein Modul, das sein Material erst holt, wenn es dran ist. Derselbe Eintritt wie am
    Start (``order_units``, ``start``-Ereignis, ``Im Prozess``, Exklusivität), nur vor
    **diesem** Modul. Keine Rückführung (das Stück kam aus dem freien Bestand); gewählt
    werden nur freie Stücke (``services/consumption``). Der ``start``-Eintrag trägt die
    Modul-``id`` – daran unterscheidet der Graph die beiden (``flow._tally``).
    """
    if not units:
        return []
    ids = _join(db, [{"order_id": order.id, "instance_unit_id": u.id,
                      "return_to_order_id": None} for u in units])
    _pass(
        db, order=order, units=units, membership_ids=ids,
        kind=KIND_START, step=step,
        status_after=st.START_AFTER, next_step_id=step.id, actor_id=actor_id,
    )
    return ids


# ---------------------------------------------------------------------------
# Schritt bestätigen
# ---------------------------------------------------------------------------

def _verified_instance(db: Session, *, order: Order, step: ProcessStep,
                       instance_object_id: Optional[int],
                       verification: Optional[str]) -> Optional[Instance]:
    """**Habe ich das richtige Ding vor mir?** — die Scan-Pflicht, serverseitig.

    Der Scan verifiziert die **Instanz** (eine Einzelinstanz hat kein Etikett). Daraus folgt
    ohne Abfrage (``materialize.plan``): Charge = EIN Scan, Einzelserialisierung = ein Scan
    je Instanz. Darum nimmt diese Stelle genau **eine** Instanz entgegen.
    """
    module = modules.get(step.module_type)
    if not module.requires_verification:
        return None
    if verification not in VERIFICATIONS:
        raise Invalid(f"«{modules.label(step.module_type)}» verlangt, dass die Instanz vor der "
                f"Eingabe bestätigt wird – gescannt oder von Hand eingegeben. Ohne diese "
                f"Angabe steht nicht fest, an welchem Ding gearbeitet wurde.")
    instance = (
        db.query(Instance).filter(Instance.object_id == instance_object_id).first()
        if instance_object_id else None
    )
    if instance is None:
        raise NotFound(f"Instanz {instance_object_id} gibt es nicht – es wurde nichts erfasst.")
    return instance


def step_of(db: Session, order: Order, step_id: int) -> ProcessStep:
    """Das Modul ``step_id`` **dieses** Auftrags – sonst 404. Die eine Nachschlage-Stelle."""
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise NotFound("Diesen Prozessschritt gibt es nicht.")
    return step


def confirm_step(
    db: Session, *, order: Order, step_id: int, values: dict[str, dict[str, Any]],
    actor_id: Optional[int],
    instance_object_id: Optional[int] = None,
    verification: Optional[str] = None,
    sources: Optional[list[int]] = None,
    place: Optional[int] = None,
    auto: bool = False,
) -> dict[str, Any]:
    """«Bestätigen» — der eine Mechanismus, den jedes Modul auslöst.

    Verifikation und Vorher-Status prüfen, festhalten, Nachher-Status setzen, loggen,
    vorrücken; am letzten Schritt passiert das Stück das **Ende-Objekt**.

    **Ein Vorgang ist EINE Instanz** (§3); ``values`` trägt je gezogener Einzelinstanz einen
    Wertesatz nach ihrer Nummer. Erfassung und Verbrauch werden **vor** dem Statuswechsel
    geprüft. ``sources``: Instanzen für den Verbrauch (leer = freier Bestand, FIFO).
    **«Nicht bestanden» rückt NICHT vor** (§4). Der Auftrag ist gesperrt (``lock_orders``).
    """
    lock_orders(db, [order.id])
    step = step_of(db, order, step_id)
    waiting = _ready_at(db, order=order, step=step, auto=auto,
                        instance_object_id=instance_object_id, verification=verification)
    units = [u for _, u in waiting]
    result = _record(db, order=order, step=step, units=units, values=values,
                     verification=verification, actor_id=actor_id)
    # **Nicht bestanden ⇒ nichts rückt vor**, auch nicht der ungezogene Rest (§4.1).
    if result == "failed":
        db.flush()
        return {"moved": 0, "held": len(units), "result": result}
    _advance(db, order=order, step=step, waiting=waiting, verification=verification,
             sources=sources, place=place, actor_id=actor_id)
    db.flush()
    # Was jetzt von selbst weiterzieht (``carry_on``). Ein Zahlungsmodul, das selbst gerade
    # durchlässt (``auto``), fragt nicht noch einmal die Zahlungsmodule – das tut die
    # Schleife, aus der es kommt.
    carry_on(db, order=order, step=step, actor_id=actor_id, payments=not auto)
    return {"moved": len(units), "held": 0, "result": result}


def _ready_at(db: Session, *, order: Order, step: ProcessStep, auto: bool,
              instance_object_id: Optional[int],
              verification: Optional[str]) -> list[tuple[OrderUnit, InstanceUnit]]:
    """**Darf hier jetzt bestätigt werden – und woran?** Die Stücke, die davorstehen."""
    current = order_status(db, order)
    if current != st.IM_PROZESS:
        raise Conflict(f"Der Auftrag ist «{st.label(current)}» – "
                    f"es gibt nichts mehr zu bestätigen.")
    # **Ein Zahlungsmodul bestätigt niemand von Hand** (``advance_payments`` ruft mit ``auto``).
    voucher_svc.assert_completable(db, step=step, auto=auto)
    instance = _verified_instance(
        db, order=order, step=step,
        instance_object_id=instance_object_id, verification=verification,
    )
    # ►► **Die Sperre der Rückführung — hier und nur hier.** ◄◄ Ein neuer Modultyp erbt sie.
    blocked = pending_returns(db, order).get(step.id)
    if blocked:
        raise Conflict(f"«{modules.label(step.module_type)}» wartet auf die Rückführung aus "
                + ("Auftrag " if len(blocked) == 1 else "den Aufträgen ")
                + ", ".join(str(n) for n in blocked)
                + ". Solange dort etwas offen ist, gehört es zu dem, was hier bearbeitet "
                  "wird – bestätigen hiesse ohne dieses Stück fortzufahren.")
    waiting = _units_at(db, order, step.id, instance_id=instance.id if instance else None)
    if not waiting:
        where = f" von Instanz {instance.object_id}" if instance else ""
        raise Conflict(f"Vor «{modules.label(step.module_type)}» steht keine Einzelinstanz"
                    f"{where} – hier ist gerade nichts zu tun.")
    for _, unit in waiting:
        if unit.status != st.IM_PROZESS:
            raise Conflict(f"Einzelinstanz {number_of(db, unit)} steht auf "
                    f"«{st.label(unit.status)}», «{modules.label(step.module_type)}» erwartet "
                    f"«{st.label(st.IM_PROZESS)}».")
    return waiting


def _record(db: Session, *, order: Order, step: ProcessStep, units: list[InstanceUnit],
            values: dict[str, dict[str, Any]], verification: Optional[str],
            actor_id: Optional[int]) -> Optional[str]:
    """**Festhalten, was das Modul festhält** – je gezogener Einzelinstanz ein Wertesatz.

    Gezogen ist, was die Stichprobe zog (``sampling.ensure`` als Netz); Ungezogene laufen
    ohne ``capture`` durch. Zurück kommt, ob ein Stück durchfiel – das hält die ganze
    Instanz an (§4.1).
    """
    sampling.ensure(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    drawn_ids = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    drawn = [u for u in units if u.id in drawn_ids]
    by_unit = _captures_for(db, step=step, drawn=drawn, values=values)
    captures = capture_svc.record_for_step(
        db, order=order, step=step, units=drawn, captures=by_unit,
    )
    if captures:
        log.process_events(db, [
            {
                "order_id": order.id, "step_id": step.id, "instance_unit_id": u.id,
                "kind": KIND_CAPTURE,
                # Erfassen ist keine Zustandsänderung – gemessen wird, was da ist.
                "status_before": u.status, "status_after": u.status,
                # **Das Urteil dieses Stücks**, nicht das der Instanz (§9.5).
                "payload": {"capture_id": captures[u.id].id,
                            "result": captures[u.id].result,
                            "verification": verification},
                "actor_id": actor_id,
            }
            for u in drawn
        ])
    results = [c.result for c in captures.values()]
    return "failed" if "failed" in results else next(iter(results), None)


def _advance(db: Session, *, order: Order, step: ProcessStep,
             waiting: list[tuple[OrderUnit, InstanceUnit]], verification: Optional[str],
             sources: Optional[list[int]], place: Optional[int],
             actor_id: Optional[int]) -> None:
    """**Das Modul wirkt, die Stücke passieren es.** Derselbe Weg für jeden Modultyp.

    Erst der Ort (``places.apply_for_step``), dann der Verbrauch (``consumption.plan``) –
    beide prüfen vor jedem Statuswechsel; Herkunft, Ziel, Verifikation reisen in den Log
    (§7.2). An einem **Ausgang** verlässt alles den Auftrag ohne das Ende-Objekt (keine
    Rückführung); sonst rückt es vor oder durch das Ende-Objekt hinaus.
    """
    module = modules.get(step.module_type)
    units = [u for _, u in waiting]
    moved = places_svc.apply_for_step(db, step=step, units=units, target=place)
    marks = {u.id: {"verification": verification, **moved.get(u.id, {})} for u in units}
    built = consumption_svc.plan(db, step=step, products=units, sources=sources)
    if built:
        _build_in(db, order=order, step=step, products=units, built=built,
                  verification=verification, actor_id=actor_id)
    following = None if module.terminal else _following(db, order, step)
    _pass(
        db, order=order, units=units, membership_ids=[m.id for m, _ in waiting],
        kind=KIND_STEP, step=step,
        status_after=(module.exit_status_for(step.config) if module.terminal
                      else st.IM_PROZESS),
        next_step_id=following.id if following else None,
        actor_id=actor_id, payloads=marks,
    )
    if module.terminal:
        return
    if following is None:
        _finish(db, order=order, rows=waiting, actor_id=actor_id)
    else:
        sampling.ensure(db, order=order, step=following, actor_id=actor_id)


def _build_in(db: Session, *, order: Order, step: ProcessStep, products: list[InstanceUnit],
              built: dict[int, list[InstanceUnit]], verification: Optional[str],
              actor_id: Optional[int]) -> None:
    """**Verbauen**: die Komponenten treten am Modul ein und gehen im selben Zug hinaus.

    Beide Übergänge laufen durch ``_pass``; **worin** steht im Payload (``into``). Danach ist
    der Träger der Ort (``places.place_in``), geräumt beim Ausbau (``places.take_out``) (§9.6).
    """
    taken = [c for group in built.values() for c in group]
    ids = _enter_at_step(db, order=order, step=step, units=taken, actor_id=actor_id)
    _pass(
        db, order=order, units=taken, membership_ids=ids,
        kind=KIND_STEP, step=step,
        status_after=modules.get(step.module_type).exit_status_for(step.config) or st.VERBAUT,
        next_step_id=None, actor_id=actor_id,
        payloads=consumption_svc.payloads(built, verification=verification),
    )
    by_product = {p.id: p for p in products}
    for product_id, components in built.items():
        places_svc.place_in(db, units=components, carrier=by_product[product_id])


def carry_on(db: Session, *, order: Order, step: Optional[ProcessStep],
             actor_id: Optional[int], payments: bool = True) -> None:
    """►►► **Was jetzt von selbst weiterzieht – EINE Stelle.** ◄◄◄

    Zwei Gründe lassen Stücke ohne Klick weiterziehen, und jeder Ort, an dem sich etwas
    ändert (bestätigt, abgezweigt, zurückgekehrt, bezahlt), fragt beide – hier, in dieser
    Reihenfolge:

    1. **Die Stichprobe ist durch** (``_run_through`` ab ``step``) – der ungezogene Rest läuft.
    2. **Ein Zahlungsmodul darf durchlassen** (``advance_payments``) – zugesagt, bezahlt.
    """
    if step is not None:
        _run_through(db, order=order, step=step, actor_id=actor_id)
        db.flush()
    if payments:
        advance_payments(db, order=order, actor_id=actor_id)
        db.flush()


def advance_payments(db: Session, *, order: Order, actor_id: Optional[int]) -> int:
    """►►► **Die Stücke ziehen durch ein Zahlungsmodul – von selbst.** ◄◄◄

    Mit der Zusage (bei Vorauszahlung mit dem Geld) dürfen sie weiter (``voucher.passable``);
    gefragt wird jedes Zahlungsmodul mit wartenden Stücken ohne ausstehende Rückführung,
    über ``confirm_step``. Gibt zurück, wie viele Stücke weitergezogen sind.
    """
    lock_orders(db, [order.id])
    # Erkannt daran, dass es einen Beleg gibt – nie am Modultyp.
    paying = [s for s in steps_of(db, order) if voucher_svc.of_step(db, s.id) is not None]
    moved = 0
    for _ in range(64):
        if not paying or order_status(db, order) != st.IM_PROZESS:
            return moved
        blocked = pending_returns(db, order)
        ready = next((s for s in paying
                      if s.id not in blocked and _units_at(db, order, s.id)
                      and voucher_svc.pass_problem(db, step=s) is None), None)
        if ready is None:
            return moved
        moved += confirm_step(db, order=order, step_id=ready.id, values={},
                              actor_id=actor_id, verification=VERIFY_MANUAL,
                              auto=True)["moved"]
    return moved


def _following(db: Session, order: Order, step: ProcessStep) -> Optional[ProcessStep]:
    """Das Modul **nach** diesem – oder ``None``, wenn danach das Ende kommt."""
    return (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.position > step.position)
        .order_by(ProcessStep.position)
        .first()
    )


def _sample_cleared(db: Session, *, order: Order, step: ProcessStep) -> bool:
    """Ist die Stichprobe **dieses Moduls** durch — und bestanden? (§4.1/§9.3)

    1. Jedes gezogene Stück, das noch im Auftrag ist, ist hier erfasst.
    2. Keines ist durchgefallen – sonst ist der ungeprüfte Rest verdächtig (ISO 2859-1).

    Ein Modul ohne Erfassungspunkte ist darum nie «durch». Gelesen wird die Ziehung
    (``sampling.drawn_ids``), nicht die heutigen Zugehörigkeiten.
    """
    drawn = sampling.drawn_ids(db, order=order, step=step)
    if not drawn:
        return False
    here = {
        int(i) for (i,) in db.query(OrderUnit.instance_unit_id).filter(
            OrderUnit.order_id == order.id, OrderUnit.released_at.is_(None)).all()
    }
    latest = _latest_captures(db, order, step, list(drawn))
    for uid in drawn:
        capture = latest.get(uid)
        if capture is None:
            if uid in here:
                return False                       # steht hier noch aus
            continue                               # weg – kann hier nicht mehr erfasst werden
        if capture.result == "failed" and uid in here:
            return False                           # hält an, solange es hier steht (§4.1)
    return True


def _run_through(db: Session, *, order: Order, step: Optional[ProcessStep],
                 actor_id: Optional[int]) -> None:
    """►►► **Wer hier nicht gezogen wurde, wird hier auch nicht gescannt.** ◄◄◄

    Erst wenn die Stichprobe durch und bestanden ist (``_sample_cleared``), passiert der
    ungezogene Rest das Modul ohne Erfassung – im Log als ``sampled: False`` (§9.3). Das
    kaskadiert über die folgenden Module (besuchte gemerkt).
    """
    seen: set[int] = set()
    while step is not None and step.id not in seen:
        seen.add(step.id)
        # **Ein terminales Modul wird nie durchlaufen** – den Ausgang bestätigt ein Mensch.
        if modules.get(step.module_type).terminal:
            return
        if not _sample_cleared(db, order=order, step=step):
            return
        here = _units_at(db, order, step.id)
        if not here:
            return
        # **Nur das Ungezogene.** Ein gezogenes Stück, das hier noch steht, wartet.
        drawn = sampling.drawn_at(db, order=order, step=step,
                                  unit_ids=[u.id for _, u in here])
        waiting = [(m, u) for m, u in here if u.id not in drawn]
        if not waiting:
            return
        units = [u for _, u in waiting]
        following = _following(db, order, step)
        _pass(
            db, order=order, units=units, membership_ids=[m.id for m, _ in waiting],
            kind=KIND_STEP, step=step, status_after=st.IM_PROZESS,
            next_step_id=following.id if following else None, actor_id=actor_id,
            payloads={u.id: {"sampled": False} for u in units},
        )
        if following is None:
            _finish(db, order=order, rows=waiting, actor_id=actor_id)
            db.flush()
            return
        sampling.ensure(db, order=order, step=following, actor_id=actor_id)
        db.flush()
        step = following


def _finish(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
            actor_id: Optional[int]) -> None:
    """Das Ende-Objekt. **Es setzt den Endzustand — es sei denn, das Stück geht weiter.**

    Kommt niemand nach, wird es frei (§4.2) bzw. **Verkauft**; kehrt es in einen Auftrag
    zurück, bleibt es **Im Prozess**. Bewegt in Gruppen mit gleichem Ziel.
    """
    back = [(m, u) for m, u in rows if m.return_to_order_id]
    stay = [(m, u) for m, u in rows if not m.return_to_order_id]
    # ►►► **Was einer anderen Partei gehört, wird «Verkauft», nicht frei.** ◄◄◄ Abgeleitet aus
    # dem jüngsten nicht stornierten Zahlungsmodul (``voucher.sold_units``).
    sold = voucher_svc.sold_units(db, [u.id for _, u in stay])
    kept = [(m, u) for m, u in stay if u.id not in sold]
    gone = [(m, u) for m, u in stay if u.id in sold]

    for group, status_after in ((kept, st.DEFAULT_END_STATUS), (gone, st.VERKAUFT),
                                (back, st.IM_PROZESS)):
        if not group:
            continue
        _pass(
            db, order=order,
            units=[u for _, u in group], membership_ids=[m.id for m, _ in group],
            kind=KIND_END, step=None,
            status_after=status_after, next_step_id=None, actor_id=actor_id,
        )
    if not back:
        return
    # ►► **Zurück heisst: dort weiter, wo es ausgeschert ist** – und gleich durch, was dort
    # schon erledigt ist (Stichprobe, zugesagtes Zahlungsmodul). ◄◄
    for home_id, at in _return_home(db, order=order, rows=back, actor_id=actor_id):
        carry_on(db, order=db.get(Order, home_id), step=db.get(ProcessStep, at),
                 actor_id=actor_id)


def _return_home(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
                 actor_id: Optional[int]) -> list[tuple[int, int]]:
    """Geliehene Stücke kehren an **genau die Stelle** zurück, an der sie ausgeschert sind.

    Die geschlossene Zeile des Quell-Auftrags trägt noch ihr ``current_step_id``; sie wieder
    zu öffnen **ist** die Rückführung (erst nachdem die eigene Zeile geschlossen ist – der
    Unique-Index prüft je Anweisung). Zurück kommen die Rückkehrpunkte ``(Auftrag, Modul)``.
    """
    lock_orders(db, {m.return_to_order_id for m, _ in rows})
    homes = {
        (m.order_id, m.instance_unit_id): m
        for m in (
            db.query(OrderUnit)
            .filter(
                OrderUnit.order_id.in_({m.return_to_order_id for m, _ in rows}),
                OrderUnit.instance_unit_id.in_({u.id for _, u in rows}),
                OrderUnit.released_at.isnot(None),
                OrderUnit.current_step_id.isnot(None),
            )
            .order_by(OrderUnit.id)
            .all()
        )
    }
    events: list[dict[str, Any]] = []
    reopen: list[int] = []
    for m, u in rows:
        home = homes.get((m.return_to_order_id, u.id))
        if home is None:
            # Die Verbindung zeigt ins Leere – das wird nicht still überspielt.
            raise Failed(f"Einzelinstanz {number_of(db, u)} sollte in Auftrag "
                    f"{_order_number(db, m.return_to_order_id)} zurückkehren, findet dort "
                    f"aber keine offene Stelle – der Datenbestand ist kaputt.")
        reopen.append(home.id)
        events.append({
            "order_id": home.order_id,
            "step_id": home.current_step_id,
            "instance_unit_id": u.id,
            "kind": KIND_RETURN,
            "status_before": st.IM_PROZESS,
            "status_after": st.IM_PROZESS,
            "payload": {"from_order": order.object_id},
            "actor_id": actor_id,
        })
    log.process_events(db, events)
    for part in _chunks(reopen):
        db.execute(
            update(OrderUnit)
            .where(OrderUnit.id.in_(part))
            .values(released_at=None)
            .execution_options(synchronize_session=False)
        )
    return sorted({(e["order_id"], e["step_id"]) for e in events})


# ---------------------------------------------------------------------------
# Die Erfassung je Stück
# ---------------------------------------------------------------------------

def _captures_for(
    db: Session, *, step: ProcessStep, drawn: list[InstanceUnit],
    values: dict[str, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Nummern → Stück-ids, und die Deckung wird **verlangt**, nicht angenommen.

    Ein Wertesatz je Einzelinstanz, geschlüsselt nach ihrer Nummer. In beiden Richtungen
    gilt: **erfasst wird, was gezogen wurde.** Ohne Erfassungspunkte ist leer das einzig
    Richtige.
    """
    points = capture_svc.points_of(step)
    if not points:
        if values:
            raise Invalid(f"«{modules.label(step.module_type)}» erfasst nichts – "
                        f"hier ist kein Wert festzuhalten.")
        return {}

    numbers = unit_numbers(db, drawn)
    by_number = {numbers[u.id]: u for u in drawn}
    unknown = sorted(set(values) - set(by_number))
    if unknown:
        raise Invalid(f"Für {', '.join(unknown)} ist hier nichts zu erfassen – "
                    f"diese Einzelinstanzen sind nicht gezogen.")
    fehlend = sorted(n for n in by_number if n not in values)
    if fehlend:
        raise Invalid(f"{len(fehlend)} von {len(by_number)} Einzelinstanzen sind noch nicht "
                f"erfasst: {', '.join(fehlend[:5])}"
                + (" …" if len(fehlend) > 5 else "")
                + ". Erfasst wird je Stück, nicht je Scan.")
    return {by_number[n].id: v for n, v in values.items()}
