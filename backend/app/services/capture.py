"""Datenerfassung — die Werte, die ein Modul an Einzelinstanzen festhält.

**Erfasst wird immer am Stück.** Die Zeile hängt an der Einzelinstanz, nicht an der
Instanz und nicht am Artikel; eine Auswertung «wie steht die Charge da?» ist eine
Summierung darüber, keine eigene Zeile. Das ist die Einzelinstanz-Regel, hier als
Fremdschlüssel.

**Was erfasst wird, sagt das Modul** (``process_steps.config``), nicht der Artikel. Die
frühere Maske am Artikel (``articles.capture_fields``) ist entfallen: sie war eine
zweite Stelle für dieselbe Frage, und sie hing an keinem Prozess – man konnte an einem
Stück erfassen, ohne dass es irgendwo davorstand.

**Erfassen ist ein Vorgang, kein Formular.** Es gibt darum keinen Endpunkt, der eine
Erfassung ohne Modul schreibt: geschrieben wird ausschliesslich hier, im selben Zug wie
der Statuswechsel (``process._pass``).

**Gelesen wird sie am Prozess, nicht am Stück** (Testnotiz #677). Die frühere Historie
am Instanz-Detail war eine zweite Ansicht auf dieselbe Sache, an einem Ort, an dem man
nicht arbeitet: erfasst wird an einem Modul, und dort steht auch, was erfasst wurde.
Die Zeilen selbst bleiben – sie sind der Nachweis, nicht die Ansicht.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from ..domain import capture_types, modules
from ..models import Capture, InstanceUnit, Order, ProcessStep

#: Erfassungspunkte, die eine **Datei** tragen. Sie werden wie jeder andere Wert erfasst;
#: der Unterschied ist nur die Eingabe (Kamera/Zeichenfläche statt Tastatur).
MEDIA = ("photo", "signature")


def points_of(step: ProcessStep) -> list[dict[str, Any]]:
    """Die Erfassungspunkte dieses Moduls. Leer heisst: hier wird nichts erfasst."""
    return modules.points_of(step.config)


def record_for_step(
    db: Session,
    *,
    order: Order,
    step: ProcessStep,
    units: list[InstanceUnit],
    values: dict[str, Any],
    actor_id: Optional[int],
) -> dict[int, Capture]:
    """Eine Erfassung für **alle** Stücke festhalten, die gerade vor dem Modul stehen.

    Geprüft wird **vor** der ersten Zeile: fehlt ein Pflichtpunkt, entsteht gar nichts.
    Eine halbe Erfassung wäre schlimmer als keine – sie sähe hinterher aus wie eine
    vollständige.

    **Ein Wertesatz, eine Zeile je Stück** (Annahme, siehe PROCESS_CORE §13): erfasst
    wird gemeinsam, gespeichert wird je Einzelinstanz. Die Datenhaltung nimmt damit die
    andere Variante (je Stück eigene Werte) bereits vorweg – sie wäre eine Änderung an
    der Eingabe, nicht am Modell.
    """
    points = points_of(step)
    capture_types.check_values(points, values)
    # **Ohne Erfassungspunkte wird nichts erfasst.** Das Aussondern im Modus «verschrotten»
    # hält nichts fest – der Scan ist die Bestätigung, und die steht als Ereignis im Log
    # (``process._pass``). Eine leere Zeile je Stück wäre ein Nachweis über nichts und
    # sähe in der Historie aus wie eine Erfassung. Geprüft wird trotzdem: ein Wert, den
    # dieses Modul nicht kennt, bleibt ein Fehler (``check_values`` oben).
    if not points:
        return {}
    result = capture_types.verdict(points, values)

    out: dict[int, Capture] = {}
    for unit in units:
        entry = Capture(
            instance_unit_id=unit.id,
            order_id=order.id,
            step_id=step.id,
            values=dict(values or {}),
            result=result,
            captured_by=actor_id,
        )
        db.add(entry)
        out[unit.id] = entry
    db.flush()
    return out
