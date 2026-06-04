from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.models.item import SerialMode, PurchaseType


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    size: Optional[str] = None
    unit: str = "Stk"
    category: Optional[str] = None
    is_equipment: bool = False
    serial_mode: SerialMode = SerialMode.unit
    is_sales_product: bool = False
    shop_description: Optional[str] = None
    purchase_type: Optional[PurchaseType] = PurchaseType.one_time
    list_price_chf: Optional[float] = None
    hs_code: Optional[str] = None
    min_stock: Optional[float] = None
    reorder_point: Optional[float] = None
    max_stock: Optional[float] = None
    preferred_supplier_id: Optional[int] = None
    lead_time_days: Optional[int] = None


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    size: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    is_equipment: Optional[bool] = None
    is_sales_product: Optional[bool] = None
    shop_description: Optional[str] = None
    purchase_type: Optional[PurchaseType] = None
    list_price_chf: Optional[float] = None
    hs_code: Optional[str] = None
    min_stock: Optional[float] = None
    reorder_point: Optional[float] = None
    max_stock: Optional[float] = None
    preferred_supplier_id: Optional[int] = None
    lead_time_days: Optional[int] = None


class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    size: Optional[str]
    unit: str
    category: Optional[str]
    is_equipment: bool
    serial_mode: SerialMode
    replaced_by_id: Optional[int]
    replaces_id: Optional[int]
    is_sales_product: bool
    shop_description: Optional[str]
    purchase_type: Optional[PurchaseType]
    list_price_chf: Optional[float]
    hs_code: Optional[str]
    min_stock: Optional[float]
    reorder_point: Optional[float]
    max_stock: Optional[float]
    preferred_supplier_id: Optional[int]
    lead_time_days: Optional[int]
    is_approved: bool
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True
