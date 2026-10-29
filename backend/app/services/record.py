"""**Was ist an diesem Modul passiert?** — das Protokoll, je Einzelinstanz.

> **Feste Regel für ALLE Module, heute und künftig** (Testnotiz #717): ein abgeschlossenes
> Modul zeigt auf Klick lückenlos, was in ihm passiert ist – jede erfasste Angabe, jedes
> Stück.

**Und darum steht sie hier und nicht in einem Modul.** Ein Protokoll je Modultyp wäre
dieselbe Ansicht n-mal, und die (n+1)-te fehlte beim nächsten Typ – genau die Sorte
Lücke, die man erst bemerkt, wenn jemand einen Nachweis braucht. Diese Datei liest den
**Ereignis-Log**, und den schreibt jedes Modul über dieselbe eine Stelle
(``process._pass``). Ein neuer Modultyp erbt das Protokoll, ohne eine Zeile dafür zu
schreiben.

**Gespeichert wird dafür nichts.** Alles steht bereits da: der Übergang im Log, die Werte
in ``captures``, die Zuordnung einer verbauten Komponente im Payload (``into``). Was
gefehlt hat, war die Ansicht.

## Ein Eintrag ist ein VORGANG, nicht ein Stück

Ein Stück kann dasselbe Modul mehrfach passieren – nach einem «nicht bestanden» wird
erneut erfasst, und beide Male sind passiert. Der Log ist append-only, also **beides**
steht drin, und beides gehört ins Protokoll. Zusammengefasst würde die Wiederholung die
Vergangenheit überschreiben.

Gebaut wird der Eintrag darum aus zwei Ereignissen, in der Reihenfolge, in der sie
geschrieben werden (``process.confirm_step``):

===============  ==========================================================
``capture``      **erfasst** – Werte, Urteil, wer, wann
``step``         **passiert** – Nachher-Zustand, Verifikation, ggf. ``into``
===============  ==========================================================

Eine Erfassung ohne folgendes ``step`` ist genau das, was «nicht bestanden» heisst: es
wurde gemessen, und es rückte nichts vor. Sie steht darum ebenfalls als Eintrag da –
gerade sie ist der interessante.

## «Nicht gezogen» kommt aus der ZIEHUNG, nicht aus einem Vermerk

Ein Stück, das ohne Erfassung durchlief, hat keinen ``capture``-Eintrag – aber daraus
allein folgt nichts: ein Modul ohne Erfassungspunkte hat für **kein** Stück einen. Die
Aussage steht im ``sample``-Ereignis, und das ist die einzige Stelle, an der sie steht
(``services/sampling``). Ein Vermerk am Übergang wäre der zweite Ort: ihn schreibt nur
**einer** der beiden Wege, die ein Stück vorrücken lassen (der Durchlauf am *nächsten*
Modul), nicht der Vorgang am eigenen – die ungezogenen Geschwister einer bestätigten
Instanz trügen ihn also nie.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session

from ..domain import capture_types, modules
from ..models import Capture, Instance, InstanceUnit, Order, ProcessEvent, ProcessStep
from ..models.process_event import KIND_CAPTURE, KIND_STEP
from . import people, sampling
from .instances import SEP, unit_numbers


@dataclass
class Value:
    """Ein erfasster Wert – mit seiner Frage, nicht nur mit seinem Schlüssel."""

    key: str
    label: str
    type: str
    value: Any
    #: Das Urteil **dieses** Punktes (``True``/``False``) – ``None``, wenn er keines hat.
    #: Ein Foto belegt, es bewertet nicht; ein erfundenes «in Ordnung» wäre eine Aussage,
    #: die niemand getroffen hat.
    ok: Optional[bool] = None


@dataclass
class Entry:
    """Ein Vorgang an diesem Modul, an **einer** Einzelinstanz."""

    number: str
    at: datetime
    actor: Optional[str] = None
    #: Wie die Instanz bestätigt wurde: ``scan`` ↔ ``manual``. Ohne den Vermerk wäre die
    #: Tastatur von der Kamera hinterher nicht zu unterscheiden.
    verification: Optional[str] = None
    #: Der Zustand **nach** dem Vorgang. ``None`` heisst: nichts rückte vor (der Fall
    #: «nicht bestanden»).
    status_after: Optional[str] = None
    #: Der Zustand **vor** dem Vorgang – erst damit ist ablesbar, ob sich überhaupt etwas
    #: geändert hat.
    #:
    #: Ein **Durchläufer** (Datenerfassung, Bewegen) führt ``Im Prozess`` → ``Im Prozess``;
    #: in jeder Zeile stünde derselbe Wert, und was in jeder Zeile gleich lautet, ist keine
    #: Information (Testnotiz #726). Bei einem **Ausgang** ist der Zustand dagegen genau
    #: das, was der Vorgang bewirkt hat.
    #:
    #: Der Dienst entscheidet das **nicht** – er liefert beide Werte, und die Anzeige
    #: fragt, ob sie verschieden sind. Ein hier weggelassener Zustand hiesse, «vorgerückt»
    #: und «nichts geändert» wären dasselbe; sie sind es nicht.
    status_before: Optional[str] = None
    #: Das Urteil der Erfassung: ``passed`` · ``failed`` · ``None`` (nichts Bewertbares).
    result: Optional[str] = None
    #: Lief dieses Stück **ohne** Erfassung durch (ausserhalb der Ziehung)?
    sampled: bool = True
    #: Nur beim Verbrauch: die Nummer des Stücks, in das hier verbaut wurde.
    into: Optional[str] = None
    values: list[Value] = field(default_factory=list)


def _points(step: ProcessStep) -> dict[str, dict[str, Any]]:
    return {p["key"]: p for p in modules.points_of(step.config)}


def _values(points: dict[str, dict[str, Any]], stored: dict[str, Any]) -> list[Value]:
    """Die gespeicherten Werte, in der **Reihenfolge der Definition** und mit ihrer Frage.

    Ein Wert zu einem Punkt, den die Definition nicht (mehr) kennt, wird trotzdem
    gezeigt – roh und mit seinem Schlüssel als Beschriftung. Ihn wegzulassen hiesse, aus
    dem Protokoll etwas zu entfernen, das erfasst wurde; ein Nachweis, der stillschweigend
    kürzt, ist keiner.
    """
    out: list[Value] = []
    for key, point in points.items():
        if key not in (stored or {}):
            continue
        raw = stored[key]
        out.append(Value(
            key=key, label=point.get("label") or key, type=point.get("type") or "text",
            value=raw, ok=capture_types.get(point["type"]).verdict(point, raw),
        ))
    for key, raw in (stored or {}).items():
        if key not in points:
            out.append(Value(key=key, label=key, type="text", value=raw))
    return out


def _entries(order: Order, step: ProcessStep):
    """**Die Vorgänge dieses Moduls als Abfrage** – je Vorgang ein Anker, in SQL gebildet.

    Ein Vorgang ist ein ``step``-Ereignis, zusammen mit der ``capture`` unmittelbar davor
    (desselben Stücks), oder eine ``capture``, auf die kein ``step`` folgt («erfasst, nicht
    bestanden»). Sortiert wird wie im Protokoll: nach Zeitpunkt des Vorgangs (die Erfassung,
    wenn es eine gibt), dann nach der Stücknummer (bytegenau, wie sie dasteht).
    """
    w = {"partition_by": ProcessEvent.instance_unit_id, "order_by": ProcessEvent.id}
    ev = (
        select(
            ProcessEvent.id, ProcessEvent.kind, ProcessEvent.instance_unit_id,
            ProcessEvent.created_at,
            func.lag(ProcessEvent.kind).over(**w).label("prev_kind"),
            func.lag(ProcessEvent.id).over(**w).label("prev_id"),
            func.lag(ProcessEvent.created_at).over(**w).label("prev_at"),
            func.lead(ProcessEvent.kind).over(**w).label("next_kind"),
        )
        .where(ProcessEvent.order_id == order.id, ProcessEvent.step_id == step.id,
               ProcessEvent.kind.in_((KIND_CAPTURE, KIND_STEP)))
        .subquery()
    )
    merged = and_(ev.c.kind == KIND_STEP, ev.c.prev_kind == KIND_CAPTURE)
    alone = and_(ev.c.kind == KIND_CAPTURE,
                 or_(ev.c.next_kind.is_(None), ev.c.next_kind != KIND_STEP))
    number = func.concat(func.lpad(cast(Instance.object_id, String), 9, "0"), SEP,
                         cast(InstanceUnit.suffix, String)).collate("C")
    at = case((merged, ev.c.prev_at), else_=ev.c.created_at)
    return (
        select(
            case((ev.c.kind == KIND_STEP, ev.c.id), else_=None).label("step_ev"),
            case((merged, ev.c.prev_id), (alone, ev.c.id), else_=None).label("capture_ev"),
        )
        .join(InstanceUnit, InstanceUnit.id == ev.c.instance_unit_id)
        .join(Instance, Instance.id == InstanceUnit.instance_id)
        .where(or_(ev.c.kind == KIND_STEP, alone))
        .order_by(at, number, ev.c.id)
    )


def step_record(db: Session, order: Order, step: ProcessStep, *,
                limit: int = 200, offset: int = 0) -> tuple[list[Entry], int]:
    """Das Protokoll dieses Moduls — **eine Seite**, gezählt und geschnitten in SQL.

    Gekappt, aber nicht verschwiegen: bei einer 6000er-Charge sind es tausende Einträge,
    und die Gesamtzahl steht daneben. Geladen wird nur, was auf der Seite steht.
    """
    query = _entries(order, step)
    total = int(db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0)
    page = db.execute(query.limit(limit).offset(offset)).all()
    if not page:
        return [], total
    ids = {i for row in page for i in row if i is not None}
    events = {e.id: e for e in db.query(ProcessEvent).filter(ProcessEvent.id.in_(ids)).all()}
    rows = list(events.values())
    points = _points(step)
    unit_ids = {int(e.instance_unit_id) for e in rows}
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(unit_ids | _into_ids(rows))).all()
    numbers = unit_numbers(db, units)
    actors = people.names(db, {int(e.actor_id) for e in rows if e.actor_id})
    # **Die Ziehung** – gelesen, nicht gerechnet. ``None`` heisst «hier wurde nie
    # gezogen»; dann ist «nicht gezogen» gar keine mögliche Antwort.
    drawn = (sampling.drawn_at(db, order=order, step=step, unit_ids=unit_ids)
             if sampling.was_drawn(db, order=order, step=step) else None)
    captures = _captures(db, {int((e.payload or {}).get("capture_id"))
                             for e in rows
                             if e.kind == KIND_CAPTURE and (e.payload or {}).get("capture_id")})
    return [
        _entry(events.get(c) if c else None, events.get(s) if s else None,
               points=points, numbers=numbers, actors=actors, drawn=drawn, captures=captures)
        for s, c in page
    ], total


def _entry(cap: Optional[ProcessEvent], passed: Optional[ProcessEvent], *, points, numbers,
           actors, drawn, captures) -> Entry:
    """Ein Vorgang aus seinen (höchstens) zwei Ereignissen: erfasst · passiert."""
    first = cap or passed
    unit_id = int(first.instance_unit_id)
    entry = Entry(
        number=numbers.get(unit_id, str(unit_id)), at=first.created_at,
        actor=actors.get(int(first.actor_id)) if first.actor_id else None,
    )
    if cap is not None:
        payload = cap.payload or {}
        capture = captures.get(int(payload.get("capture_id") or 0))
        entry.verification = payload.get("verification")
        entry.result = payload.get("result")
        entry.values = _values(points, capture.values if capture else {})
    if passed is not None:
        payload = passed.payload or {}
        entry.status_after = passed.status_after
        entry.status_before = passed.status_before
        entry.verification = payload.get("verification") or entry.verification
        entry.sampled = drawn is None or unit_id in drawn
        into = payload.get("into")
        if into is not None:
            entry.into = numbers.get(int(into), str(into))
    return entry


def _into_ids(rows: list[ProcessEvent]) -> set[int]:
    return {
        int((e.payload or {}).get("into"))
        for e in rows if (e.payload or {}).get("into") is not None
    }


def _captures(db: Session, ids: set[int]) -> dict[int, Capture]:
    if not ids:
        return {}
    return {c.id: c for c in db.query(Capture).filter(Capture.id.in_(ids)).all()}
