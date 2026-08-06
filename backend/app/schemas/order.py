"""Auftrag – API-Form.

Der Auftrag trägt heute nur seine Identität. ``OrderCreate`` ist darum bewusst offen:
was ein Entwurf mitbringt, entscheidet sich mit den Pflichteingaben
(``services/orders.validate_draft``) – bis dahin nimmt der Endpunkt entgegen, was kommt,
und die eine Regel entscheidet, ob es reicht.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    """Der Entwurf, so wie ihn die Oberfläche schickt.

    Offen gehalten, nicht aus Nachlässigkeit: ein festes Feldschema wäre eine Behauptung
    darüber, was ein Auftrag braucht – und genau das ist noch nicht entschieden. Geprüft
    wird ausschliesslich in ``services/orders.validate_draft``.
    """

    model_config = ConfigDict(extra="allow")


class OrderValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf speicherbar?».

    Damit legt die Oberfläche denselben Massstab an wie der Server, ohne die Regel ein
    zweites Mal zu formulieren.
    """

    saveable: bool
    missing: list[str] = Field(
        default_factory=list,
        description="Namen der fehlenden Pflichteingaben – leer heisst speicherbar.",
    )


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class OrderSummary(BaseModel):
    """Feed-Zeile. Identisch zur Detail-Antwort, solange der Auftrag nichts weiter trägt –
    getrennt gehalten, weil das Detail wächst, sobald die Prozesslogik steht."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
