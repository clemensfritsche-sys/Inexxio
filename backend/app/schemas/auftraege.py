from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuftragCreate(BaseModel):
    item_id: int
    menge: Decimal = Field(default=Decimal("1"), gt=0)
    datum_faellig: Optional[date] = None
    notiz: Optional[str] = None
    wiederkehrend: bool = False
    intervall_typ: Optional[str] = None
    intervall_wert: Optional[str] = None
    naechste_faelligkeit: Optional[date] = None


class AuftragUpdate(BaseModel):
    menge: Optional[Decimal] = None
    datum_faellig: Optional[date] = None
    status: Optional[str] = None
    notiz: Optional[str] = None
    wiederkehrend: Optional[bool] = None
    intervall_typ: Optional[str] = None
    intervall_wert: Optional[str] = None
    naechste_faelligkeit: Optional[date] = None


class AuftragResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    menge: Decimal
    datum_faellig: Optional[date] = None
    status: str
    notiz: Optional[str] = None
    wiederkehrend: bool
    intervall_typ: Optional[str] = None
    intervall_wert: Optional[str] = None
    naechste_faelligkeit: Optional[date] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    item_name: Optional[str] = None


class AuftragListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    menge: Decimal
    datum_faellig: Optional[date] = None
    status: str
    wiederkehrend: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    item_name: Optional[str] = None
