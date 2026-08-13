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

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import capture_types, modules
from ..models import Capture, InstanceUnit, Order, ProcessEvent, ProcessStep, UserProfile
from ..models.process_event import KIND_CAPTURE, KIND_STEP
from . import sampling


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


def step_record(db: Session, order: Order, step: ProcessStep, *,
                limit: int = 200, offset: int = 0) -> tuple[list[Entry], int]:
    """Das Protokoll dieses Moduls — **eine** Abfrage über den Log, seitenweise.

    Gekappt, aber nicht verschwiegen: bei einer 6000er-Charge sind es tausende Einträge,
    und die Gesamtzahl steht daneben. Wer sie alle sehen will, blättert.
    """
    rows = db.execute(
        select(ProcessEvent)
        .where(
            ProcessEvent.order_id == order.id,
            ProcessEvent.step_id == step.id,
            ProcessEvent.kind.in_((KIND_CAPTURE, KIND_STEP)),
        )
        .order_by(ProcessEvent.id)
    ).scalars().all()
    if not rows:
        return [], 0

    points = _points(step)
    unit_ids = {int(e.instance_unit_id) for e in rows}
    numbers = _numbers(db, unit_ids | _into_ids(rows))
    actors = _actors(db, {int(e.actor_id) for e in rows if e.actor_id})
    # **Die Ziehung** – gelesen, nicht gerechnet. ``None`` heisst «hier wurde nie
    # gezogen»; dann ist «nicht gezogen» gar keine mögliche Antwort.
    drawn = (sampling.drawn_at(db, order=order, step=step, unit_ids=unit_ids)
             if sampling.was_drawn(db, order=order, step=step) else None)
    captures = _captures(db, {int((e.payload or {}).get("capture_id"))
                             for e in rows
                             if e.kind == KIND_CAPTURE and (e.payload or {}).get("capture_id")})

    entries: list[Entry] = []
    open_rows: dict[int, Entry] = {}
    for ev in rows:
        unit_id = int(ev.instance_unit_id)
        payload = ev.payload or {}
        if ev.kind == KIND_CAPTURE:
            capture = captures.get(int(payload.get("capture_id") or 0))
            entry = Entry(
                number=numbers.get(unit_id, str(unit_id)),
                at=ev.created_at,
                actor=actors.get(int(ev.actor_id)) if ev.actor_id else None,
                verification=payload.get("verification"),
                result=payload.get("result"),
                values=_values(points, capture.values if capture else {}),
            )
            # Eine zweite Erfassung ohne dazwischenliegendes Vorrücken ersetzt die erste
            # nicht – beide sind passiert. Die vorherige wird darum geschlossen.
            if unit_id in open_rows:
                entries.append(open_rows.pop(unit_id))
            open_rows[unit_id] = entry
            continue

        entry = open_rows.pop(unit_id, None) or Entry(
            number=numbers.get(unit_id, str(unit_id)), at=ev.created_at,
            actor=actors.get(int(ev.actor_id)) if ev.actor_id else None,
        )
        entry.status_after = ev.status_after
        entry.verification = payload.get("verification") or entry.verification
        entry.sampled = drawn is None or unit_id in drawn
        into = payload.get("into")
        if into is not None:
            entry.into = numbers.get(int(into), str(into))
        entries.append(entry)

    # Was offen blieb, ist der Fall «erfasst, nicht bestanden» – er gehört ins Protokoll.
    entries.extend(open_rows.values())
    entries.sort(key=lambda e: (e.at, e.number))
    return entries[offset:offset + limit], len(entries)


def _into_ids(rows: list[ProcessEvent]) -> set[int]:
    return {
        int((e.payload or {}).get("into"))
        for e in rows if (e.payload or {}).get("into") is not None
    }


def _numbers(db: Session, unit_ids: set[int]) -> dict[int, str]:
    from .process import unit_numbers

    if not unit_ids:
        return {}
    units = db.query(InstanceUnit).filter(InstanceUnit.id.in_(unit_ids)).all()
    return unit_numbers(db, units)


def _actors(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return {
        u.id: u.display_name
        for u in db.query(UserProfile).filter(UserProfile.id.in_(ids)).all()
    }


def _captures(db: Session, ids: set[int]) -> dict[int, Capture]:
    if not ids:
        return {}
    return {c.id: c for c in db.query(Capture).filter(Capture.id.in_(ids)).all()}
