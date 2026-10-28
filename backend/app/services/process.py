"""**Der Prozess zur Laufzeit: Modul bestätigen, weiterziehen, ankommen, zurückkehren.**

Die eine Stelle, an der Einzelinstanzen ihren Status wechseln (``_pass`` – auch die
Freigabe, ``services/release``, schreibt durch sie). Jeder Wechsel schreibt
im selben Atemzug einen Eintrag in den Ereignis-Log (Ebene 3) und zieht die Projektionen
nach (Ebene 2) — es gibt keinen zweiten Schreibweg, und darum können die beiden nicht
auseinanderlaufen.

Gelesen wird PROCESS_CORE.md; hier steht nur, was daraus folgt.
"""

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from ..models import (
    Instance, InstanceUnit, Order, OrderUnit, ProcessEvent,
    ProcessStep,
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

#: Wie die Instanz vor der Eingabe verifiziert wurde. **Beides ist eine Bestätigung** –
#: die Tastatur ist die Alternative zum Scan, nicht seine Umgehung, und beides steht im
#: Log. Ohne den Vermerk wäre «getippt» von «gescannt» hinterher nicht zu unterscheiden,
#: und die Scan-Pflicht wäre eine Behauptung.
VERIFY_SCAN, VERIFY_MANUAL = "scan", "manual"
VERIFICATIONS = (VERIFY_SCAN, VERIFY_MANUAL)


# ---------------------------------------------------------------------------
# Der Ereignis-Log — die EINE Schreibstelle für einen Statuswechsel
# ---------------------------------------------------------------------------

def _assert_not_terminal(db: Session, units: list[InstanceUnit], status_after: str) -> None:
    """►►► **Ein Endzustand wird nicht überschrieben.** ◄◄◄

    Die Prüfung sitzt hier, weil hier **jeder** Statuswechsel durchläuft (§4.1): Start,
    Modul, Ende – es gibt keinen zweiten Schreibweg, und darum gibt es auch keinen Weg an
    ihr vorbei. Ein neues Modul erbt sie, ohne von ihr zu wissen; es fragt gar nicht, ob
    es darf, ihm wird gesagt, dass es nicht darf.

    **An der falschen Stelle wäre sie eine Hoffnung.** Sie am Modul zu prüfen hiesse: an
    jedem Modul, für immer, und beim ersten vergessenen ist der Endzustand weg. Sie in der
    Freigabe zu prüfen deckt nur den Eintritt ab – ``release`` tut das ohnehin
    (``is_selectable``), aber nur für **freie** Stücke; ein Stück, das noch in einem
    Auftrag liegt, kommt dort gar nicht an dieser Prüfung vorbei.

    **Und darunter liegt der Trigger** (``statuses.terminal_guard_sql``): dieselbe Regel
    als Eigenschaft der Tabelle. Diese Stelle hier gibt es nicht, weil die Datenbank
    unsicher wäre, sondern damit der Fehler einen **Satz** hat statt einer rohen
    Datenbank-Meldung – und damit er den Vorgang abbricht, bevor irgendetwas geschrieben
    ist.
    """
    stuck = [u for u in units if st.is_terminal(u.status)]
    if not stuck:
        return
    first = stuck[0]
    raise HTTPException(
        status_code=409,
        detail=(
            f"Einzelinstanz {number_of(db, first)} ist «{st.label(first.status)}» – das ist "
            f"ein Endzustand. Er wird nicht überschrieben"
            + (f" (versucht: «{st.label(status_after)}»)" if status_after else "")
            + (f"; betroffen sind {len(stuck)} Stücke" if len(stuck) > 1 else "")
            + ". Was passiert ist, ist passiert."
        ),
    )


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
    _assert_not_terminal(db, units, status_after)

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

    # ►► **Jedes Stück behält seinen Ort – ausser es ist endgültig weg.** ◄◄ Gesperrt liegt
    # im Sperrlager, Verkauft noch in der Halle bis zur Abholung, Verbaut im Träger (der
    # Verbrauch setzt ihn). Die Regel hängt am **Status** und steht darum hier, an der
    # EINEN Stelle, an der ein Status geschrieben wird.
    if st.is_terminal(status_after):
        places_svc.forget(db, units)
    return len(units)


def lock_orders(db: Session, order_ids: Iterable[int]) -> None:
    """►►► **Aufträge sperren, bevor an ihnen geschrieben wird** – in fester Reihenfolge. ◄◄◄

    Jeder Schreibweg an einem laufenden Auftrag (Bestätigen, die Stücke durch ein
    Zahlungsmodul ziehen, die Übernahme aus ihm, die Rückkehr in ihn) nimmt zuerst diese
    Zeilensperre. Damit lesen zwei gleichzeitige Vorgänge am selben Auftrag nie denselben
    Stand: der zweite wartet, bis der erste festgeschrieben ist, und sieht dann dessen
    Ergebnis – die Stichprobe wird einmal gezogen, ein Stück einmal bewegt. Sortiert nach
    ``id``, damit zwei Vorgänge, die mehrere Aufträge sperren, sich nicht gegenseitig
    blockieren. Innerhalb derselben Transaktion ist eine zweite Sperre derselben Zeile frei.
    """
    ids = sorted({int(i) for i in order_ids})
    if ids:
        db.execute(select(Order.id).where(Order.id.in_(ids)).order_by(Order.id)
                   .with_for_update())


def _join(db: Session, rows: list[dict[str, Any]]) -> list[int]:
    """Die Zugehörigkeiten anlegen – **ein Stück in genau einem Auftrag** (§3).

    Die Sperren davor schliessen den Wettlauf aus; bleibt doch ein Verstoss gegen den
    partiellen Unique-Index, ist das ein 409 mit der Nummer des Stücks, nicht eine rohe
    Datenbankmeldung. Der Savepoint hält die Transaktion dafür lesbar.
    """
    try:
        with db.begin_nested():
            db.execute(insert(OrderUnit), rows)
    except IntegrityError as exc:
        found = re.search(r"\(instance_unit_id\)=\((\d+)\)", str(exc.orig))
        unit = db.get(InstanceUnit, int(found.group(1))) if found else None
        name = f"Einzelinstanz {number_of(db, unit)}" if unit else "Eine Einzelinstanz"
        raise HTTPException(
            status_code=409,
            detail=(f"{name} läuft inzwischen in einem anderen Auftrag – die Auswahl ist "
                    f"veraltet. Bitte prüfen und erneut freigeben."),
        ) from None
    return [int(i) for (i,) in db.query(OrderUnit.id).filter(
        OrderUnit.order_id == rows[0]["order_id"],
        OrderUnit.instance_unit_id.in_([r["instance_unit_id"] for r in rows]),
        OrderUnit.released_at.is_(None),
    ).all()]


def _enter_at_step(db: Session, *, order: Order, step: ProcessStep,
                   units: list[InstanceUnit], actor_id: Optional[int]) -> list[int]:
    """►►► **Der zweite Eintrittspunkt: ein Stück tritt an einem MODUL in den Auftrag.** ◄◄◄

    Für ein Modul, das sich sein Material erst holt, wenn es dran ist (``release`` kennt
    nur das Start-Objekt).

    **Verallgemeinert ist der Punkt, nicht der Mechanismus.** Es ist derselbe Eintritt –
    dieselbe Zeile in ``order_units``, dasselbe ``start``-Ereignis, derselbe Übergang auf
    ``Im Prozess``, dieselbe Exklusivität (der partielle Unique-Index greift ab jetzt).
    Nur die Antwort auf «und wo steht es dann?» ist eine andere: nicht vor dem ersten
    Modul, sondern vor **diesem**.

    Zwei Dinge stehen bewusst nicht hier:

    * **Keine Rückführung.** Wer an einem Modul eintritt, kam aus dem freien Bestand und
      hat keinen Auftrag, in den er zurückkönnte (``return_to_order_id`` bleibt ``NULL``).
    * **Kein Schutz gegen einen laufenden Halter.** Den gibt es schon: die Auswahl der
      Stücke passiert eine Ebene höher und nimmt ausschliesslich freie
      (``services/consumption``); wäre eines doch gebunden, wiese es der Unique-Index ab.

    Der ``start``-Eintrag trägt hier – anders als am Start-Objekt – die Modul-``id``.
    Genau daran unterscheidet der Graph die beiden (``flow._tally``): das Start-Objekt hat
    passiert, wer oben hereinkam; wer an einem Modul eintritt, hat es nie gesehen.
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

    Der Scan verifiziert die **Instanz**, nicht die Einzelinstanz — und das ist keine
    Vereinfachung, sondern die einzige Möglichkeit: eine Einzelinstanz zieht bewusst
    keine Objektnummer (``models/instance_unit``), ein Etikett kann es für sie also gar
    nicht geben. Das physische Etikett klebt am physischen Ding, und das Ding **ist** die
    Instanz – die Kiste, die Maschine.

    Daraus fällt der Unterschied Charge ↔ Einzelserialisierung von selbst heraus, ohne
    eine einzige Abfrage danach (``materialize.plan``)::

        Charge, Menge 3              →  (1, 3)  eine Instanz   →  EIN Scan
        Einzelserialisierung, Menge 3 → (3, 1)  drei Instanzen →  DREI Scans

    Ein Vorgang je Instanz, ein Scan je Vorgang. Deshalb nimmt diese Ausführungsstelle
    genau **eine** Instanz entgegen und nicht «alles, was davorsteht».
    """
    module = modules.get(step.module_type)
    if not module.requires_verification:
        return None
    if verification not in VERIFICATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{modules.label(step.module_type)}» verlangt, dass die Instanz vor der "
                f"Eingabe bestätigt wird – gescannt oder von Hand eingegeben. Ohne diese "
                f"Angabe steht nicht fest, an welchem Ding gearbeitet wurde."
            ),
        )
    instance = (
        db.query(Instance).filter(Instance.object_id == instance_object_id).first()
        if instance_object_id else None
    )
    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"Instanz {instance_object_id} gibt es nicht – es wurde nichts erfasst.",
        )
    return instance


def step_of(db: Session, order: Order, step_id: int) -> ProcessStep:
    """Das Modul ``step_id`` **dieses** Auftrags – sonst 404. Die eine Nachschlage-Stelle."""
    step = (
        db.query(ProcessStep)
        .filter(ProcessStep.order_id == order.id, ProcessStep.id == step_id)
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Diesen Prozessschritt gibt es nicht.")
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

    Prüft die Verifikation, prüft den Vorher-Status, lässt das Modul festhalten was es
    festhält, setzt den Nachher-Status, loggt, rückt vor. Ist der Schritt der letzte,
    passiert das Stück im selben Zug das **Ende-Objekt** und wird frei.

    **Ein Vorgang ist EINE Instanz** (§3): der Scan verifiziert sie. **Die Erfassung
    dagegen gilt der Einzelinstanz** – ``values`` trägt einen eigenen Wertesatz je
    gezogenem Stück, geschlüsselt nach seiner Nummer.

    **Erfassung und Verbrauch liegen VOR dem Statuswechsel**: fehlt ein Pflichtpunkt oder
    reicht der Bestand nicht, ist das ein Fehler mit Namen – und es hat sich nichts bewegt.
    ``sources`` sind die Instanzen, aus denen verbraucht werden soll (leer = der ganze
    freie Bestand, FIFO).

    **«Nicht bestanden» rückt NICHT vor** (§4): die Feststellung ist geloggt, die Stücke
    bleiben stehen, und was daraus folgt, entscheidet ein Mensch.

    **Der Auftrag ist gesperrt, solange das läuft** (``lock_orders``): zwei gleichzeitige
    Vorgänge am selben Auftrag laufen nacheinander.
    """
    lock_orders(db, [order.id])
    step = step_of(db, order, step_id)
    waiting = _ready_at(db, order=order, step=step, auto=auto,
                        instance_object_id=instance_object_id, verification=verification)
    units = [u for _, u in waiting]
    result = _record(db, order=order, step=step, units=units, values=values,
                     verification=verification, actor_id=actor_id)
    # **Nicht bestanden ⇒ nichts rückt vor.** Auch die nicht gezogenen Stücke dieser
    # Instanz bleiben stehen: die Stichprobe ist nicht mehr repräsentativ, der ungeprüfte
    # Rest verdächtig (§4.1).
    if result == "failed":
        db.flush()
        return {"moved": 0, "held": len(units), "result": result}
    _advance(db, order=order, step=step, waiting=waiting, verification=verification,
             sources=sources, place=place, actor_id=actor_id)
    db.flush()
    # **Was hier nicht gezogen wurde, läuft jetzt mit** (§9.3) – siehe ``_run_through``.
    _run_through(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    # ►► **Ein Zahlungsmodul weiter hinten lässt durch, was es darf.** ◄◄ Nur beim Klick
    # eines Menschen – ``advance_payments`` ruft hier selbst mit ``auto``.
    if not auto:
        advance_payments(db, order=order, actor_id=actor_id)
    return {"moved": len(units), "held": 0, "result": result}


def _ready_at(db: Session, *, order: Order, step: ProcessStep, auto: bool,
              instance_object_id: Optional[int],
              verification: Optional[str]) -> list[tuple[OrderUnit, InstanceUnit]]:
    """**Darf hier jetzt bestätigt werden – und woran?** Die Stücke, die davorstehen."""
    current = order_status(db, order)
    if current != st.IM_PROZESS:
        raise HTTPException(
            status_code=409,
            detail=(f"Der Auftrag ist «{st.label(current)}» – "
                    f"es gibt nichts mehr zu bestätigen."),
        )
    # **Ein Zahlungsmodul bestätigt niemand von Hand** – die Stücke ziehen von selbst
    # weiter, sobald sie dürfen (``advance_payments`` ruft hier mit ``auto``).
    voucher_svc.assert_completable(db, step=step, auto=auto)
    instance = _verified_instance(
        db, order=order, step=step,
        instance_object_id=instance_object_id, verification=verification,
    )
    # ►► **Die Sperre der Rückführung — hier und nur hier.** ◄◄ Am EINEN
    # Ausführungs-Mechanismus, den jedes Modul auslöst; ein neuer Modultyp erbt sie.
    blocked = pending_returns(db, order).get(step.id)
    if blocked:
        raise HTTPException(
            status_code=409,
            detail=(
                f"«{modules.label(step.module_type)}» wartet auf die Rückführung aus "
                + ("Auftrag " if len(blocked) == 1 else "den Aufträgen ")
                + ", ".join(str(n) for n in blocked)
                + ". Solange dort etwas offen ist, gehört es zu dem, was hier bearbeitet "
                  "wird – bestätigen hiesse ohne dieses Stück fortzufahren."
            ),
        )
    waiting = _units_at(db, order, step.id, instance_id=instance.id if instance else None)
    if not waiting:
        where = f" von Instanz {instance.object_id}" if instance else ""
        raise HTTPException(
            status_code=409,
            detail=(f"Vor «{modules.label(step.module_type)}» steht keine Einzelinstanz"
                    f"{where} – hier ist gerade nichts zu tun."),
        )
    for _, unit in waiting:
        if unit.status != step.status_before:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Einzelinstanz {number_of(db, unit)} steht auf "
                    f"«{st.label(unit.status)}», «{modules.label(step.module_type)}» erwartet "
                    f"«{st.label(step.status_before)}»."
                ),
            )
    return waiting


def _record(db: Session, *, order: Order, step: ProcessStep, units: list[InstanceUnit],
            values: dict[str, dict[str, Any]], verification: Optional[str],
            actor_id: Optional[int]) -> Optional[str]:
    """**Festhalten, was das Modul festhält** – je gezogener Einzelinstanz ein Wertesatz.

    Gezogen ist, was die Stichprobe beim Erreichen gezogen hat (``sampling.ensure`` ist
    idempotent und steht hier als Netz). Die **nicht** gezogenen laufen ohne Erfassung
    durch; sichtbar ist das, weil sie keinen ``capture``-Eintrag haben. **Eine
    durchgefallene Einzelinstanz hält die ganze Instanz an** (§4.1): das Urteil je Stück
    steht in seiner Zeile, zurück kommt, ob eines fiel.
    """
    sampling.ensure(db, order=order, step=step, actor_id=actor_id)
    db.flush()
    drawn_ids = sampling.drawn_at(db, order=order, step=step, unit_ids=[u.id for u in units])
    drawn = [u for u in units if u.id in drawn_ids]
    by_unit = _captures_for(db, step=step, drawn=drawn, values=values)
    captures = capture_svc.record_for_step(
        db, order=order, step=step, units=drawn, captures=by_unit, actor_id=actor_id,
    )
    if captures:
        db.execute(insert(ProcessEvent), [
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

    Erst der **Ort** (``places.apply_for_step``), dann der **Verbrauch**
    (``consumption.plan``) – beide prüfen, bevor sich ein Status ändert, und beide geben
    für ein Modul, das nichts bewegt bzw. nichts verbaut, nichts zurück. Was dabei passiert
    ist (Herkunft, Ziel, Verifikation), reist als Payload in den Log (§7.2).

    An einem **Ausgang** (``Module.terminal``) verlässt alles den Auftrag mit dem
    Ausgangszustand und passiert das Ende-Objekt **nicht** – dort hängt die Rückführung,
    und ein ausgesondertes Stück kehrt nirgends zurück. Sonst rückt es zum nächsten Modul
    vor (dort wird jetzt gezogen) oder durch das Ende-Objekt hinaus.
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
                      else step.status_after),
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

    Die beiden Übergänge des Statuswegs ``Freigegeben`` → ``Im Prozess`` → ``Verbaut``
    gehen beide durch ``_pass``, also stehen beide im Log. **Worin** steht im Payload
    (``into``) – das ist die ganze Genealogie (§3). Danach ist der **Träger** der neue Ort
    (``places.place_in``): dieses Stück, nicht seine Instanz. Der Zeiger sagt, wo es jetzt
    liegt, und wird beim Ausbau geräumt (``places.take_out``); die Genealogie im Log
    bleibt (§9.6).
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


def advance_payments(db: Session, *, order: Order, actor_id: Optional[int]) -> int:
    """►►► **Die Stücke ziehen durch ein Zahlungsmodul – von selbst.** ◄◄◄

    Es gibt dort keinen Knopf: mit der Zusage (bei einer Vorauszahlung mit dem Geld) dürfen
    die Stücke weiter (``voucher.passable``). Gefragt wird nach **jedem** Zahlungsmodul
    dieses Auftrags, vor dem Stücke stehen und das nicht auf eine Rückführung wartet.
    Derselbe Weg wie jeder andere (``confirm_step``), also dieselbe Spur im Log.

    Endlich: jeder Durchgang bewegt Stücke nach hinten, und ein Prozess ist azyklisch.
    Gibt zurück, wie viele Stücke weitergezogen sind.
    """
    lock_orders(db, [order.id])
    # **Erkannt daran, dass es einen Beleg gibt** – nie am Modultyp. Einmal gelesen: die
    # Belege entstehen mit der Freigabe.
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
    """Ist die Stichprobe **dieses Moduls** durch — und bestanden?

    Zwei Bedingungen, beide aus §4.1/§9.3, keine davon typabhängig:

    1. **Jedes gezogene Stück ist hier erfasst.** Solange eines aussteht, ist die
       Stichprobe nicht durch – auch wenn es noch bei einem Modul davor steht.
    2. **Keines ist durchgefallen.** Ein negatives Urteil hält an, und zwar alles: die
       Stichprobe ist damit nicht mehr repräsentativ, der ungeprüfte Rest verdächtig
       (ISO 2859-1). Ihn ausgerechnet dann durchlaufen zu lassen wäre das stille
       Weiterlaufen, das §4.5 verhindert.

    **Ein Modul ohne Erfassungspunkte ist damit nie «durch»** – es erfasst nichts, also
    hat kein gezogenes Stück eine Erfassung. Genau richtig: beim Aussondern **ist** der
    Scan die Bestätigung, und die kann niemand einsparen. Das steht hier als Folge, nicht
    als Abfrage nach dem Modultyp.

    **Gelesen wird die Ziehung, nicht die Gegenwart** (``sampling.drawn_ids``): ein
    gezogenes Stück, das erfasst wurde und weitergezogen ist, hält keine offene
    Zugehörigkeit mehr. Wer nur die aktuelle Liste fragt, hielte die Stichprobe für leer –
    und liesse den Rest gerade dann durchlaufen, wenn noch nichts erfasst ist.

    **Ein Stück, das den Auftrag verlassen hat, hält nichts mehr auf.** Nimmt eine
    Abweichung den Durchfaller mit, kann er hier nie mehr erfasst werden; auf ihn zu
    warten wäre eine Sackgasse ohne Ausgang.
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

    Die Zahl der Scans folgt der Stichprobe, nicht umgekehrt:

    ==========================  ==================================================
    **Zahl der Erfassungen**    Einzelinstanzen in der Stichprobe
    **Zahl der Scans**          **Instanzen**, zu denen diese gehören
    ==========================  ==================================================

    **Bewegt wird es hier**, und zwar erst, wenn die Stichprobe dieses Moduls durch
    und bestanden ist (``_sample_cleared``). Nicht schon bei der Ankunft: fällt die
    Stichprobe durch, ist der ungeprüfte Rest verdächtig und darf den Betrieb nicht
    längst verlassen haben.

    Danach ist, was hier noch steht, genau der ungezogene Rest – ein gezogenes Stück wäre
    entweder erfasst (und vorgerückt) oder durchgefallen (und dann wäre nichts «durch»).
    Es passiert das Modul regulär, nur ohne Erfassung; im Log steht das als
    ``sampled: False``, also **sichtbar** statt stillschweigend (§9.3).

    Und es **kaskadiert**: am nächsten Modul kann dieselbe Instanz wieder ausserhalb der
    Ziehung liegen. Die Schleife merkt sich die besuchten Module – ein Prozess ist endlich
    und azyklisch, aber ein Wächter kostet hier nichts.
    """
    seen: set[int] = set()
    while step is not None and step.id not in seen:
        seen.add(step.id)
        # **Ein terminales Modul wird nie durchlaufen.** Es ist ein Ausgang (§4.6): was
        # dort passiert, verlässt den Auftrag endgültig, und das bestätigt ein Mensch.
        if modules.get(step.module_type).terminal:
            return
        if not _sample_cleared(db, order=order, step=step):
            return
        here = _units_at(db, order, step.id)
        if not here:
            return
        # **Nur das Ungezogene.** Ein gezogenes Stück, das noch hier steht, ist eine
        # andere Sache – es wartet, weil ein Geschwister durchgefallen ist, und es
        # weiterzubewegen wäre eine Entscheidung, die niemand getroffen hat.
        drawn = sampling.drawn_at(db, order=order, step=step,
                                  unit_ids=[u.id for _, u in here])
        waiting = [(m, u) for m, u in here if u.id not in drawn]
        if not waiting:
            return
        units = [u for _, u in waiting]
        following = _following(db, order, step)
        _pass(
            db, order=order, units=units, membership_ids=[m.id for m, _ in waiting],
            kind=KIND_STEP, step=step, status_after=step.status_after,
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

    Das ist eine Regel, keine Fallunterscheidung: das Ende-Objekt reicht das Stück an
    den weiter, der als Nächstes kommt. Kommt niemand, wird es frei (§4.2) – oder
    **Verkauft**, wenn es einer anderen Partei gehört. Kommt der Auftrag, aus dem es
    geliehen war, bleibt es **Im Prozess** – es ist ja in einem.

    Die Stücke bewegen sich dabei in **Gruppen mit gleichem Ziel**, nicht einzeln: ein
    Auftrag kann geliehene und eigene Stücke gleichzeitig ans Ende bringen.
    """
    back = [(m, u) for m, u in rows if m.return_to_order_id]
    stay = [(m, u) for m, u in rows if not m.return_to_order_id]
    # ►►► **Was einer anderen Partei gehört, wird «Verkauft», nicht frei.** ◄◄◄ Wem es
    # gehört, sagt das jüngste nicht stornierte Zahlungsmodul, das es passiert hat
    # (``voucher.sold_units``) – keine gespeicherte Kopie, also wirkt ein Storno von selbst.
    # «Verkauft» ist Historie wie «Verbaut»: kein Bestand, kein FIFO, greifen nur als
    # Abweichung.
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
    # ►► **Zurück heisst: dort weiter, wo es ausgeschert ist.** ◄◄ Steht es vor einem Modul,
    # dessen Stichprobe inzwischen erledigt ist, oder vor einem zugesagten Zahlungsmodul,
    # wartete es sonst auf einen Vorgang, den niemand mehr verlangt.
    for home_id, at in _return_home(db, order=order, rows=back, actor_id=actor_id):
        home = db.get(Order, home_id)
        _run_through(db, order=home, step=db.get(ProcessStep, at), actor_id=actor_id)
        db.flush()
        advance_payments(db, order=home, actor_id=actor_id)


def _return_home(db: Session, *, order: Order, rows: list[tuple[OrderUnit, InstanceUnit]],
                 actor_id: Optional[int]) -> list[tuple[int, int]]:
    """Geliehene Stücke kehren an **genau die Stelle** zurück, an der sie ausgeschert sind.

    Die Stelle steht bereits da: die Zeile des Quell-Auftrags wurde beim Ausscheren
    geschlossen, ihr ``current_step_id`` aber nicht angetastet. Sie wieder zu öffnen
    **ist** die Rückführung – es gibt nichts nachzuschlagen und nichts zu berechnen.

    Möglich ist das erst hier, weil die Zeile dieses Auftrags eine Anweisung vorher
    geschlossen wurde: der partielle Unique-Index lässt genau eine offene Zugehörigkeit
    je Stück zu, und er prüft je Anweisung. Die Heimat-Aufträge sind gesperrt, bevor in
    sie geschrieben wird; zurück kommen ihre Rückkehrpunkte ``(Auftrag, Modul)``.
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
            # Die Verbindung zeigt ins Leere. Das darf nicht sein und wird nicht
            # stillschweigend überspielt: ein Stück, das nirgends ankommt, wäre für
            # jeden Bestand und jede Historie ein Loch.
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Einzelinstanz {number_of(db, u)} sollte in Auftrag "
                    f"{_order_number(db, m.return_to_order_id)} zurückkehren, findet dort "
                    f"aber keine offene Stelle – der Datenbestand ist kaputt."
                ),
            )
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
    db.execute(insert(ProcessEvent), events)
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

    Der Aufrufer schickt einen Wertesatz je Einzelinstanz, geschlüsselt nach ihrer
    **Nummer** – die sichtbare Identität, dieselbe, die auf dem Bildschirm steht. Interne
    ids kommen an der Oberfläche nicht vor.

    Geprüft wird in beide Richtungen, und beide Male ist es dieselbe Aussage: **erfasst
    wird, was gezogen wurde.**

    * Ein Satz für ein Stück, das **nicht gezogen** ist, wäre ein Nachweis über etwas,
      das an diesem Modul nie geprüft werden sollte.
    * Ein **fehlender** Satz wäre eine Lücke, die hinterher aussieht wie «durchgelaufen,
      nichts gemessen» – dabei war die Messung verlangt.

    Ohne Erfassungspunkte gibt es nichts zu decken (Aussondern: der Scan ist die
    Bestätigung); dann ist ein leerer Satz nicht nur erlaubt, sondern der einzige
    richtige.
    """
    points = capture_svc.points_of(step)
    if not points:
        if values:
            raise HTTPException(
                status_code=400,
                detail=(f"«{modules.label(step.module_type)}» erfasst nichts – "
                        f"hier ist kein Wert festzuhalten."),
            )
        return {}

    numbers = unit_numbers(db, drawn)
    by_number = {numbers[u.id]: u for u in drawn}
    unknown = sorted(set(values) - set(by_number))
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(f"Für {', '.join(unknown)} ist hier nichts zu erfassen – "
                    f"diese Einzelinstanzen sind nicht gezogen."),
        )
    fehlend = sorted(n for n in by_number if n not in values)
    if fehlend:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{len(fehlend)} von {len(by_number)} Einzelinstanzen sind noch nicht "
                f"erfasst: {', '.join(fehlend[:5])}"
                + (" …" if len(fehlend) > 5 else "")
                + ". Erfasst wird je Stück, nicht je Scan."
            ),
        )
    return {by_number[n].id: v for n, v in values.items()}
