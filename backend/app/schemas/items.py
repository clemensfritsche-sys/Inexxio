from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    size: Optional[str] = None
    unit: str = "Stk"
    category: Optional[str] = None
    is_equipment: bool = False
    serial_mode: str = "unit"
    is_sales_product: bool = False
    shop_description: Optional[str] = None
    purchase_type: str = "one_time"
    list_price_chf: Optional[Decimal] = None
    hs_code: Optional[str] = None
    min_stock: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    max_stock: Optional[Decimal] = None
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
    purchase_type: Optional[str] = None
    list_price_chf: Optional[Decimal] = None
    hs_code: Optional[str] = None
    min_stock: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    max_stock: Optional[Decimal] = None
    preferred_supplier_id: Optional[int] = None
    lead_time_days: Optional[int] = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    size: Optional[str]
    unit: str
    category: Optional[str]
    is_equipment: bool
    serial_mode: str
    replaced_by_id: Optional[int]
    replaces_id: Optional[int]
    is_sales_product: bool
    shop_description: Optional[str]
    purchase_type: str
    list_price_chf: Optional[Decimal]
    hs_code: Optional[str]
    min_stock: Optional[Decimal]
    reorder_point: Optional[Decimal]
    max_stock: Optional[Decimal]
    preferred_supplier_id: Optional[int]
    lead_time_days: Optional[int]
    is_approved: bool
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    current_stock: Decimal
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: str
    category: Optional[str]
    is_approved: bool
    is_equipment: bool
    current_stock: Decimal
    list_price_chf: Optional[Decimal]
    created_at: datetime
    is_active: bool
