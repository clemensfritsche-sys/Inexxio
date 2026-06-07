from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ObjektCreate(BaseModel):
    item_id: int
    auftrag_id: Optional[int] = None
    typ: str
    batch_menge: Optional[Decimal] = None
    lagerort: Optional[str] = None
    gueltig_bis: Optional[date] = None


class ObjektUpdate(BaseModel):
    status: Optional[str] = None
    lagerort: Optional[str] = None
    gueltig_bis: Optional[date] = None
    batch_verbleibend: Optional[Decimal] = None
    schritt_protokoll: Optional[list[dict[str, Any]]] = None


class ObjektResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    auftrag_id: Optional[int] = None
    typ: str
    batch_menge: Optional[Decimal] = None
    batch_verbleibend: Optional[Decimal] = None
    status: str
    lagerort: Optional[str] = None
    gueltig_bis: Optional[date] = None
    schritt_protokoll: Optional[list[dict[str, Any]]] = None
    created_at: datetime
    item_name: Optional[str] = None
