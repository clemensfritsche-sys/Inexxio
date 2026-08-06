"""Auftrag – API-Form.

Der Entwurf kommt in **einem** Aufruf an: Einzelinstanzen und Prozessschritte zusammen.
Das ist keine Bequemlichkeit, sondern die Folge aus PROCESS_CORE.md §6.3 – der Auftrag
entsteht erst bei der Freigabe, und die ist eine Transaktion. Zwei Aufrufe hiessen zwei
Transaktionen und damit die Möglichkeit eines halben Auftrags.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProcessStepInput(BaseModel):
    """Ein Prozessschrittmodul, wie es der Entwurf schickt.

    ``status_before``/``status_after`` sind **Pflicht** – ein Modul ohne definierten
    Übergang ist nicht anlegbar (§4). Geprüft wird der Wert gegen die geschlossene Liste
    in ``domain/statuses.assert_known``, nicht hier: eine zweite Aufzählung im Schema
    wäre eine zweite Wahrheit.
    """

    module_type: str
    name: str = Field(min_length=1, max_length=120)
    status_before: str
    status_after: str


class OrderCreate(BaseModel):
    """Der Entwurf, so wie ihn die Oberfläche schickt."""

    unit_numbers: list[str] = Field(default_factory=list)
    steps: list[ProcessStepInput] = Field(default_factory=list)


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


class OrderUnitResponse(BaseModel):
    """Ein Stück im Auftrag – wo es steht und wie es steht."""

    instance_unit_id: int
    number: str
    status: str
    #: ``None`` = am Ende angekommen (bzw. noch nicht gestartet).
    current_step_id: Optional[int] = None
    #: ``False`` = das Stück hat den Auftrag verlassen und ist wieder frei.
    active: bool


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

    steps: list[ProcessStepResponse] = Field(default_factory=list)
    units: list[OrderUnitResponse] = Field(default_factory=list)
    events: list[ProcessEventResponse] = Field(default_factory=list)
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


class UnitOption(BaseModel):
    """Eine wählbare Einzelinstanz für die Definition.

    ``blocked_by`` nennt den Auftrag, in dem das Stück gerade aktiv ist – damit die
    Oberfläche den Grund zeigen kann, statt eine Zeile stumm auszugrauen.
    """

    number: str
    status: str
    article_name: Optional[str] = None
    available: bool
    blocked_by: Optional[int] = None
