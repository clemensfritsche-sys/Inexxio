from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RecurringOrderCreate(BaseModel):
    """Anlage eines wiederkehrenden Vorgangs (Compliance/Termin oder Abo).

    Erzeugt automatisch normale Aufträge: ``process_id`` + Subjekt (Artikel+Menge
    oder Instanz). Takt entweder fester Intervall (``interval_days``, Abo) oder
    ablauf-verankert (``valid_until`` − ``lead_time_days``, Compliance)."""

    name: str
    process_id: Optional[int] = None
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    subject_instance_id: Optional[int] = None
    interval_days: Optional[int] = None
    lead_time_days: int = 0
    validity_days: Optional[int] = None
    next_due_at: Optional[date] = None
    valid_until: Optional[date] = None

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Name fehlt")
        return v

    @field_validator("interval_days", "validity_days")
    @classmethod
    def _pos(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Anzahl Tage muss grösser als 0 sein")
        return v

    @field_validator("lead_time_days")
    @classmethod
    def _non_neg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Vorlaufzeit darf nicht negativ sein")
        return v


class RecurringOrderUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    process_id: Optional[int] = None
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    subject_instance_id: Optional[int] = None
    interval_days: Optional[int] = None
    lead_time_days: Optional[int] = None
    validity_days: Optional[int] = None
    next_due_at: Optional[date] = None
    valid_until: Optional[date] = None
    is_active: Optional[bool] = None


class RecurringOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    name: str
    status: str
    process_id: Optional[int] = None
    article_id: Optional[int] = None
    quantity: Optional[int] = None
    subject_instance_id: Optional[int] = None
    interval_days: Optional[int] = None
    lead_time_days: int = 0
    validity_days: Optional[int] = None
    next_due_at: Optional[date] = None
    valid_until: Optional[date] = None
    last_order_id: Optional[int] = None
    last_run_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # denormalisiert
    process_name: Optional[str] = None
    article_name: Optional[str] = None
    due_now: bool = False   # ist ein Auftrag fällig (zur Anzeige)
