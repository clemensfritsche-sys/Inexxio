from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemSignatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    signed_by: int
    signed_at: datetime
    signed_by_name: Optional[str] = None


class InvalidateRequest(BaseModel):
    replaced_by_id: Optional[int] = None


class SetReplacementRequest(BaseModel):
    replaced_by_id: int


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    name_id: Optional[int] = None
    unit: str = Field(default="Stk", max_length=10)
    batch_allowed: bool = False
    order_number: Optional[str] = Field(None, max_length=100)
    order_link: Optional[str] = Field(None, max_length=500)
    onshape_link: Optional[str] = Field(None, max_length=500)
    weight_g: Optional[Decimal] = None
    dim_1_mm: Optional[Decimal] = None
    dim_2_mm: Optional[Decimal] = None
    dim_3_mm: Optional[Decimal] = None
    surface_id: Optional[int] = None
    purchase_price: Optional[Decimal] = None
    purchase_currency: str = Field(default="CHF", max_length=3)
    lead_time_days: Optional[int] = None
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None
    is_sales_product: bool = False
    sales_price: Optional[Decimal] = None
    sales_currency: str = Field(default="CHF", max_length=3)
    category_id: Optional[int] = None
    vat_rate: Optional[str] = Field(None, max_length=5)
    shop_description_long: Optional[str] = None
    seo_title: Optional[str] = Field(None, max_length=200)
    seo_description: Optional[str] = None
    hs_code: Optional[str] = Field(None, max_length=20)
    serialization_type: str = Field(default="none")

    @model_validator(mode="after")
    def validate_fields(self) -> "ItemCreate":
        d1, d2, d3 = self.dim_1_mm, self.dim_2_mm, self.dim_3_mm
        if d1 is not None and d2 is not None and d1 > d2:
            raise ValueError("dim_1_mm must be <= dim_2_mm")
        if d2 is not None and d3 is not None and d2 > d3:
            raise ValueError("dim_2_mm must be <= dim_3_mm")
        if self.is_sales_product:
            if not self.sales_price:
                raise ValueError("sales_price required when is_sales_product is true")
            if not self.category_id:
                raise ValueError("category_id required when is_sales_product is true")
            if not self.vat_rate:
                raise ValueError("vat_rate required when is_sales_product is true")
        return self


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    name_id: Optional[int] = None
    unit: Optional[str] = Field(None, max_length=10)
    batch_allowed: Optional[bool] = None
    order_number: Optional[str] = Field(None, max_length=100)
    order_link: Optional[str] = Field(None, max_length=500)
    onshape_link: Optional[str] = Field(None, max_length=500)
    weight_g: Optional[Decimal] = None
    dim_1_mm: Optional[Decimal] = None
    dim_2_mm: Optional[Decimal] = None
    dim_3_mm: Optional[Decimal] = None
    surface_id: Optional[int] = None
    purchase_price: Optional[Decimal] = None
    purchase_currency: Optional[str] = Field(None, max_length=3)
    lead_time_days: Optional[int] = None
    is_sales_product: Optional[bool] = None
    sales_price: Optional[Decimal] = None
    sales_currency: Optional[str] = Field(None, max_length=3)
    category_id: Optional[int] = None
    vat_rate: Optional[str] = Field(None, max_length=5)
    shop_description_long: Optional[str] = None
    seo_title: Optional[str] = Field(None, max_length=200)
    seo_description: Optional[str] = None
    hs_code: Optional[str] = Field(None, max_length=20)
    serialization_type: Optional[str] = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_id: Optional[int]
    unit: str
    status: str
    batch_allowed: bool
    order_number: Optional[str]
    order_link: Optional[str]
    onshape_link: Optional[str]
    weight_g: Optional[Decimal]
    dim_1_mm: Optional[Decimal]
    dim_2_mm: Optional[Decimal]
    dim_3_mm: Optional[Decimal]
    surface_id: Optional[int]
    purchase_price: Optional[Decimal]
    purchase_currency: str
    lead_time_days: Optional[int]
    stock_total: Decimal
    stock_reserved: Decimal
    replaced_by_id: Optional[int]
    replaces_id: Optional[int]
    is_sales_product: bool
    sales_price: Optional[Decimal]
    sales_currency: str
    category_id: Optional[int]
    vat_rate: Optional[str]
    shop_description_long: Optional[str]
    seo_title: Optional[str]
    seo_description: Optional[str]
    hs_code: Optional[str]
    submitted_at: Optional[datetime]
    submitted_by: Optional[int]
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    submitted_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    created_by_name: Optional[str] = None
    bom_weight_g: Optional[Decimal] = None
    bom_has_lines: bool = False
    serialization_type: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    signatures: list[ItemSignatureResponse]
    replaced_by_name: Optional[str] = None
    replaces_item_name: Optional[str] = None


class ItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: str
    status: str
    batch_allowed: bool
    purchase_price: Optional[Decimal]
    purchase_currency: str
    sales_price: Optional[Decimal]
    sales_currency: str
    stock_total: Decimal
    stock_reserved: Decimal
    is_sales_product: bool
    serialization_type: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
