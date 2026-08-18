"""**Das Modul «Bewegen»** – die Fuhren und ihr Vollzug (PROCESS_CORE §9.8, ADR 009).

Dieses Modul bringt Einzelinstanzen an einen Halter. Es tut dabei **genau eines**: es
schreibt den Ort (``services/places``). Kein Status, keine Zugehörigkeit, kein Eintrag im
Ereignis-Log über das hinaus, was die eine Ausführungsstelle ohnehin schreibt.

**Zwei Körnungen, streng getrennt:**

* **Vorgang** – ein Scan = eine Instanz, wie überall im Framework (§4.4).
* **Fuhre** – ein Paar (Ausgangsort → Ziel). Zwei Ausgangsorte sind **zwei** Fuhren, weil
  es physisch zwei Transporte sind: zwei Preise, zwei Etiketten, zwei Ankünfte. Drei
  Stücke am selben Ort sind **eine** Fuhre.

Die Fuhre ist **abgeleitet, nicht eingestellt**: sie ist die Gruppierung der
davorstehenden Stücke nach ihrem heutigen Halter. Wer sie einstellen liesse, böte eine
Entscheidung an, deren richtige Antwort die Physik längst getroffen hat.

**Was dieses Modul NICHT tut** (ADR 009 §2.1, die teuerste Altlast): es liest den Ort
**nie**, um zu entscheiden, *welche* Stücke es anfasst. Die Arbeitsmenge kommt von der
Ausführungsstelle (``process._units_at``); der Ort bestimmt allein die **Gruppierung**.
Der Vorgänger hatte hier drei Zweige und vier Ausnahmen darin – und damit kamen Verkauf,
Retoure, Reservierung und Sperre in der Bewegung an.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import modules
from ..models import InstanceUnit, ProcessStep
from . import objects as obj, places


@dataclass
class Haul:
    """Eine Fuhre: was von **einem** Ausgangsort an das Ziel geht.

    ``internal`` ist **gerechnet**, nie gespeichert: gleiche Anschrift → intern, sonst
    Versand (§15.4). Der Vorgänger hat diese Klassifikation gespeichert und zwei
    Migrationen gebraucht, um die Werte wieder loszuwerden.
    """

    to_holder: int
    unit_ids: list[int] = field(default_factory=list)
    #: ``None`` = für diese Stücke gibt es noch keine Beobachtung. Das ist kein Fehler:
    #: der Kontext-Scan stellt den Ausgangsort beim Ausführen fest (§15.3).
    from_holder: Optional[int] = None
    internal: bool = True

    @property
    def known(self) -> bool:
        return self.from_holder is not None

    @property
    def pieces_count(self) -> int:
        """Wie viele Stücke diese Fuhre trägt. Gezählt, nie gespeichert."""
        return len(self.unit_ids)


def hauls(db: Session, *, step: ProcessStep, units: list[InstanceUnit]) -> list[Haul]:
    """Die **Vorschau**: was ginge von wo nach wo, gruppiert nach heutigem Halter.

    Für jedes Modul **ohne** Ziel eine leere Liste – die Oberfläche braucht damit keine
    Fallunterscheidung nach dem Modultyp (dieselbe Form wie ``StepNeed`` beim Verbrauch).

    Massgeblich für die **Ausführung** ist trotzdem der Kontext-Scan, nicht diese
    Vorschau: eine Beobachtung kann veraltet sein, ein Scan ist die Gegenwart.
    """
    target = modules.target_of(step.config)
    if not target or not units:
        return []

    current = places.current(db, [u.id for u in units])
    groups: dict[Optional[int], list[int]] = {}
    for u in units:
        groups.setdefault(current.get(u.id), []).append(u.id)

    out = [
        Haul(to_holder=target, unit_ids=ids, from_holder=src,
             internal=src is None or places.same_place(db, src, target))
        for src, ids in groups.items()
    ]
    # Stabile Reihenfolge: bekannte Orte zuerst, aufsteigend – damit zwei Aufrufe
    # dieselbe Liste ergeben und die Oberfläche nicht springt.
    out.sort(key=lambda h: (h.from_holder is None, h.from_holder or 0))
    return out


def record_for_step(
    db: Session, *, step: ProcessStep, units: list[InstanceUnit],
    from_holder_object_id: Optional[int], actor_id: Optional[int],
) -> Optional[dict[str, Any]]:
    """Den Ort schreiben – der ganze Effekt dieses Moduls.

    **No-op für jedes Modul ohne Ziel.** Genau wie ``capture_svc.record_for_step`` und
    ``consumption_svc.plan`` wird das hier bedingungslos gerufen; die Fallunterscheidung
    nach dem Modultyp entsteht aus der **Konfiguration**, nicht aus einem ``if`` an der
    Ausführungsstelle.

    **Der Kontext-Scan ist Pflicht** (§15.3, O5): ohne Ausgangsort passiert nichts – und
    zwar mit einem Satz, nicht mit einem ausgegrauten Feld. Ein Vorgabewert wäre ein Ort,
    den niemand gescannt hat.

    Gibt die Angaben zurück, die an das Schritt-Ereignis gehängt werden (``from``/``to``),
    oder ``None``, wenn dieses Modul nichts bewegt.
    """
    target = modules.target_of(step.config)
    if not target:
        return None
    if not from_holder_object_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "«Bewegen» braucht zuerst den Ausgangsort: scannen Sie, wo Sie stehen. "
                "Ohne ihn stünde nicht fest, woher die Stücke kommen – und ob es ein "
                "Versand ist."
            ),
        )
    source = int(from_holder_object_id)

    # **Die Adresse entscheidet, nicht der Halter** (§15.4). Ein Regalwechsel innerhalb
    # desselben Werks ist kein Transport; ein Weg an eine andere Anschrift ist einer –
    # und der braucht eine Vergabe, bevor irgendetwas als «dort angekommen» gilt.
    if not places.same_place(db, source, target):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Von {obj.obj_nr(source)} nach {obj.obj_nr(target)} ist ein **Versand** "
                f"(andere Anschrift). Dafür braucht es eine Vergabe an einen Dritten – "
                f"sie ist noch nicht gebaut. Innerbetriebliche Wege gehen bereits."
            ),
        )

    places.record(db, [u.id for u in units], target, actor_id=actor_id)
    return {"from": source, "to": target}
