"""Der Ort – die API-Form (PROCESS_CORE §15).

Ein Halter ist eine **Objektnummer**; daneben steht kein Typfeld, sondern ein
**abgeleiteter** Typ, damit die Oberfläche das richtige Symbol wählen kann. Er ist
Auskunft, nicht Eingabe: geschrieben wird ausschliesslich die Nummer.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HolderRef(BaseModel):
    """Ein Halter, aufgelöst. ``type``/``name`` sind ``None``, wenn die Nummer ins Leere
    zeigt – das ist dann die Aussage und wird in der Oberfläche **gemeldet**, nicht als
    «kein Ort» gezeigt (SYSTEM_LOGIC O2.4)."""

    object_id: int
    #: instance | organization | user | ``None`` (nicht auflösbar)
    type: Optional[str] = None
    name: Optional[str] = None


class PlaceHop(BaseModel):
    """Eine Station der Kette. Die **Anschrift** am Ende trägt keine Objektnummer – sie
    ist kein Datensatz und darum nicht anklickbar."""

    object_id: Optional[int] = None
    #: instance | organization | user | address | ``None``
    type: Optional[str] = None
    name: Optional[str] = None


class PlaceObservation(BaseModel):
    """Eine Beobachtung – eine Zeile der Historie."""

    id: int
    holder: HolderRef
    #: scan | tracking – ohne den Vermerk wäre eine gemeldete Ankunft von einem echten
    #: Scan nicht zu unterscheiden.
    source: str
    actor_name: Optional[str] = None
    created_at: datetime


class UnitPlaceResponse(BaseModel):
    """«Wo ist dieses Stück?» – der aktuelle Ort und seine Kette nach aussen.

    ``holder is None`` heisst **nicht bekannt**: das Stück hat noch keine Beobachtung.
    Das ist die ehrliche Antwort; ein geratener Ort wäre die Alternative.
    """

    instance_unit_id: int
    number: str
    holder: Optional[HolderRef] = None
    #: Von innen nach aussen: Behälter → Halle → Werk → Anschrift.
    chain: list[PlaceHop] = Field(default_factory=list)
    #: Befunde, keine Kosmetik – eine stumm gekappte Kette läse sich wie die ganze Wahrheit.
    chain_truncated: bool = False
    chain_cycle: bool = False
    history: list[PlaceObservation] = Field(default_factory=list)
    history_truncated: bool = False


class HeldUnit(BaseModel):
    """Ein Stück, das hier liegt."""

    instance_unit_id: int
    number: str
    instance_object_id: int
    article_name: Optional[str] = None
    status: str


class HolderContents(BaseModel):
    """«Was liegt hier?» – seitenweise, mit Gesamtzahl daneben.

    Nie alles auf einmal: bei einer 5000er-Charge wäre die volle Liste ein Vielfaches
    des Datensatzes, an dem sie hängt.
    """

    holder: HolderRef
    units: list[HeldUnit] = Field(default_factory=list)
    total: int = 0


class PlaceResult(BaseModel):
    """Die Quittung einer Ablage – bewusst schlank.

    Sie nennt, was geschah, nicht den ganzen Zustand danach: eine Antwort, die je Stück
    Kette und Historie mitschickte, wäre bei einer 500er-Charge ein Vielfaches des
    Vorgangs. Wer den Ort sehen will, fragt ihn (``GET …/places/unit/{id}``).
    """

    placed: int
    holder: HolderRef


class PlaceCreate(BaseModel):
    """Die Ablage.

    **Der Kontext-Scan hat keinen Vorgabewert** (SYSTEM_LOGIC O5): ``holder_object_id``
    ist Pflicht und kommt aus dem ersten Scan des Arbeitsgangs («wo bin ich»). Es gibt
    keinen gemerkten, geerbten oder vorbelegten Ort – wer nicht scannt, legt nicht ab.

    Ein Auftrag wird **nicht** verlangt: eine Ablage muss auch ohne Prozess möglich sein,
    und genau diese Unabhängigkeit ist die Robustheit (§15.1).
    """

    holder_object_id: int
    instance_unit_ids: list[int] = Field(min_length=1)
    #: scan (Regelfall) | tracking (ein Dritter hat gemeldet)
    source: str = "scan"
