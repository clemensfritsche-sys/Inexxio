"""Datenerfassung — die Werte, die ein Modul an Einzelinstanzen festhält.

**Erfasst wird immer am Stück** (Fremdschlüssel auf ``instance_units``); die Charge ist
eine Summierung. **Was erfasst wird, sagt das Modul** (``process_steps.config``).

**Erfassen ist ein Vorgang, kein Formular**: geschrieben nur hier, gerufen von
``process.confirm_step`` **vor** dem Statuswechsel. Gelesen wird am Prozess, nicht am Stück.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..domain import capture_types, modules
from ..models import Capture, InstanceUnit, Order, ProcessStep


def points_of(step: ProcessStep) -> list[dict[str, Any]]:
    """Die Erfassungspunkte dieses Moduls. Leer heisst: hier wird nichts erfasst."""
    return modules.points_of(step.config)


def record_for_step(
    db: Session,
    *,
    order: Order,
    step: ProcessStep,
    units: list[InstanceUnit],
    captures: dict[int, dict[str, Any]],
) -> dict[int, Capture]:
    """Die Erfassungen festhalten — **je Einzelinstanz einen eigenen Wertesatz**.

    ►►► **Der Scan verifiziert die Instanz. Die Erfassung gilt der Einzelinstanz.** ◄◄◄

    Das Etikett klebt an der Instanz; eine Messung gilt **einem Stück**. Aus einem Scan
    werden **n** Erfassungen, die Zahl folgt aus der Ziehung. Geprüft wird jeder Satz
    **vor** der ersten Zeile: fehlt ein Pflichtpunkt, entsteht nichts. Das **Urteil hängt
    am Stück**; was für die Instanz folgt, entscheidet der Aufrufer (§4.1).
    """
    points = points_of(step)
    for values in captures.values():
        capture_types.check_values(points, values)
    # **Ohne Erfassungspunkte wird nichts erfasst.** Das Aussondern im Modus «verschrotten»
    # hält nichts fest – der Scan ist die Bestätigung, und die steht als Ereignis im Log
    # (``process._pass``). Eine leere Zeile je Stück wäre ein Nachweis über nichts und
    # sähe in der Historie aus wie eine Erfassung. Geprüft wird trotzdem: ein Wert, den
    # dieses Modul nicht kennt, bleibt ein Fehler (``check_values`` oben).
    if not points:
        return {}

    out: dict[int, Capture] = {}
    for unit in units:
        values = captures.get(unit.id)
        if values is None:
            continue
        entry = Capture(
            instance_unit_id=unit.id,
            order_id=order.id,
            step_id=step.id,
            values=dict(values),
            result=capture_types.verdict(points, values),
        )
        db.add(entry)
        out[unit.id] = entry
    db.flush()
    return out
