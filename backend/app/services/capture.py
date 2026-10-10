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
    actor_id: Optional[int],
) -> dict[int, Capture]:
    """Die Erfassungen festhalten — **je Einzelinstanz einen eigenen Wertesatz**.

    ►►► **Der Scan verifiziert die Instanz. Die Erfassung gilt der Einzelinstanz.** ◄◄◄

    Das sind zwei Dinge, und sie dürfen nie gekoppelt sein. Der Scan ist eine Aussage
    über das **physische Ding**: das Etikett klebt an der Instanz, eine Einzelinstanz
    zieht keine Objektnummer. Eine Messung dagegen ist eine Aussage über **ein Stück** –
    zwei Schrauben aus derselben Charge haben zwei Durchmesser.

    Vorher stand hier **ein** Wertesatz, der auf jedes gezogene Stück kopiert wurde. Das
    war nicht bloss unbequem, es war eine **Behauptung**: bei einer Charge über zwei
    Stück entstanden zwei Messwerte, gemessen wurde einer. Ein Nachweis, der mehr Zeilen
    hat als Messungen, ist keiner – und aus derselben Kopie wären bei 1500 gezogenen
    Stücken 1500 identische «Messungen» geworden.

    Aus einem Scan werden damit **n** Erfassungen: Charge über 2 → 2, Stichprobe ¼ von
    6000 → 1500. Es gibt hier keine Abfrage nach der Serialisierung; die Zahl folgt aus
    der Ziehung.

    Geprüft wird **vor** der ersten Zeile, und zwar jeder Satz einzeln: fehlt irgendwo
    ein Pflichtpunkt, entsteht gar nichts. Eine halbe Erfassung wäre schlimmer als keine –
    sie sähe hinterher aus wie eine vollständige.

    Das **Urteil hängt am Stück**: jede Zeile trägt ihr eigenes. Was daraus für die
    Instanz folgt, entscheidet der Aufrufer (§4.1: eine durchgefallene Stichprobe hält
    die ganze Instanz an).
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
            captured_by=actor_id,
        )
        db.add(entry)
        out[unit.id] = entry
    db.flush()
    return out
