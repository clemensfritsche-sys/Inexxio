"""Auftrag – API-Form.

Der Entwurf kommt in **einem** Aufruf an: Definitionszeilen und Prozessschritte zusammen.
Das ist keine Bequemlichkeit, sondern die Folge aus PROCESS_CORE.md §6.3 – der Auftrag
entsteht erst bei der Freigabe, und die ist eine Transaktion. Zwei Aufrufe hiessen zwei
Transaktionen und damit die Möglichkeit eines halben Auftrags.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .process import ModuleInput


class DefinitionLine(BaseModel):
    """Eine Definitionszeile: Artikel · Menge · Herkunft.

    ``quantity`` referenziert **immer exakt Einzelinstanzen** – nie Instanzen und nie
    eine Artikelmenge. Bei ``origin='lager'`` müssen genau so viele ``unit_numbers``
    dabeistehen; bei ``origin='neu'`` bleiben sie leer, weil die Stücke erst bei der
    Freigabe entstehen.
    """

    article_object_id: int
    quantity: int = Field(ge=1)
    origin: str
    unit_numbers: list[str] = Field(default_factory=list)


class OrderCreate(BaseModel):
    """Der Entwurf, so wie ihn die Oberfläche schickt."""

    lines: list[DefinitionLine] = Field(default_factory=list)
    #: Der modellierte Prozess. Ein Auftrag mit einer ``Neu``-Zeile **ignoriert** ihn:
    #: sein Prozess ist die Vorlage des Artikels, als Kopie. Etwas anderes zu schicken
    #: änderte daran nichts.
    steps: list[ModuleInput] = Field(default_factory=list)


class OrderValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf freigebbar?» – ohne etwas anzulegen."""

    saveable: bool
    missing: list[str] = Field(
        default_factory=list,
        description="Was noch fehlt – leer heisst freigebbar.",
    )


class ProcessStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    module_type: str
    name: str
    status_before: str
    status_after: str
    #: Was der Modultyp braucht – bei der Datenerfassung die Erfassungspunkte.
    config: Optional[dict] = None
    #: Gesetzt, wenn dieser Schritt die **Kopie** eines Artikel-Erzeugungsprozesses ist.
    source_article_id: Optional[int] = None
    source_version: Optional[int] = None


class OrderLineResponse(BaseModel):
    """Eine festgeschriebene Definitionszeile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    quantity: int
    origin: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None


class UnitGroup(BaseModel):
    """Wie viele Stücke stehen an einer Stelle, in welchem Zustand.

    Die Datenhaltung bleibt **pro Einzelinstanz** – dies ist die Darstellungsfrage. Bei
    5000 Stück ist der Unterschied nicht Geschmack, sondern der zwischen einer Zeile und
    5000. Die einzelnen Nummern holt ``GET …/units``, wenn jemand aufklappt.
    """

    #: ``None`` = am Ende angekommen (bzw. noch nicht gestartet).
    current_step_id: Optional[int] = None
    status: str
    #: ``False`` = die Stücke haben den Auftrag verlassen und sind wieder frei.
    active: bool
    count: int


class OrderUnitResponse(BaseModel):
    """Ein einzelnes Stück im Auftrag – wo es steht und wie es steht."""

    instance_unit_id: int
    number: str
    status: str
    current_step_id: Optional[int] = None
    active: bool


class OrderUnitPage(BaseModel):
    """Eine Seite Einzelinstanzen – auf Abruf, wenn eine Gruppe aufgeklappt wird."""

    units: list[OrderUnitResponse] = Field(default_factory=list)
    total: int


class ProcessEventResponse(BaseModel):
    """Ein Eintrag im Ereignis-Log. Append-only – es gibt keinen Schreib-Pfad hierauf."""

    id: int
    kind: str
    step_id: Optional[int] = None
    unit_number: str
    status_before: str
    status_after: str
    actor: Optional[str] = None
    created_at: datetime


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    status: str
    end_status: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    lines: list[OrderLineResponse] = Field(default_factory=list)
    steps: list[ProcessStepResponse] = Field(default_factory=list)
    #: Gezählt, nicht aufgelistet – siehe ``UnitGroup``.
    unit_groups: list[UnitGroup] = Field(default_factory=list)
    events: list[ProcessEventResponse] = Field(default_factory=list)
    #: Wie viele Einträge der Log **insgesamt** hat. Ist er länger als ``events``, sagt
    #: die Oberfläche das – ein stumm gekappte Liste sähe aus wie die ganze Wahrheit.
    event_count: int = 0
    #: Welches Modul ist jetzt dran – **abgeleitet**, nicht gespeichert.
    active_step_id: Optional[int] = None


class OrderSummary(BaseModel):
    """Feed-Zeile. Ohne Schritte, Stücke und Historie – die kommen mit dem Detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ArticleOption(BaseModel):
    """Ein wählbarer Artikel für eine Definitionszeile.

    ``template_steps`` ist die Zahl der Module im Erzeugungsprozess. Sie steht hier,
    damit die Oberfläche «Neu» sperren **und den Grund nennen** kann – ohne Vorlage kann
    ein Erzeugungsauftrag nichts erzeugen.
    """

    object_id: int
    name: str
    serialization: str
    unit: str
    template_steps: int


class UnitOption(BaseModel):
    """Eine wählbare Einzelinstanz für eine ``Lager``-Zeile.

    ``blocked_by`` nennt den Auftrag, in dem das Stück gerade aktiv ist – damit die
    Oberfläche den Grund zeigen kann, statt eine Zeile stumm auszugrauen.
    """

    number: str
    status: str
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    available: bool
    blocked_by: Optional[int] = None
