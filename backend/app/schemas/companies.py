from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AddressSchema(BaseModel):
    street: Optional[str] = None
    street_nr: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: str = "CH"


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1)
    company_type: str
    uid: Optional[str] = None
    vat_id: Optional[str] = None
    address: Optional[AddressSchema] = None
    country_code: str = "CH"
    iban: Optional[str] = None
    payment_term_days: int = 30
    notes: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    company_type: Optional[str] = None
    uid: Optional[str] = None
    vat_id: Optional[str] = None
    address: Optional[AddressSchema] = None
    country_code: Optional[str] = None
    iban: Optional[str] = None
    payment_term_days: Optional[int] = None
    notes: Optional[str] = None


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company_type: str
    uid: Optional[str]
    vat_id: Optional[str]
    vat_validated_at: Optional[datetime]
    address: Optional[dict]
    country_code: str
    iban: Optional[str]
    payment_term_days: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ContactCreate(BaseModel):
    company_id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_primary: Optional[bool] = None


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    is_primary: bool
    created_at: datetime
    is_active: bool
