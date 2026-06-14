from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

ALLOWED_STATUS = ("draft", "released", "inactive")
# Regal, Palettenplatz, Boden, Schublade, Kommissionierzone, Aussenlager
ALLOWED_TYPES = ("rack", "pallet", "floor", "drawer", "picking", "external")


def _check_type(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    if v not in ALLOWED_TYPES:
        raise ValueError(f"Typ muss eine von {', '.join(ALLOWED_TYPES)} sein")
    return v


def _check_status(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in ALLOWED_STATUS:
        raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
    return v


def _check_lat(v: Optional[Decimal]) -> Optional[Decimal]:
    if v is None:
        return v
    if not (Decimal("-90") <= v <= Decimal("90")):
        raise ValueError("Breitengrad muss zwischen -90 und 90 liegen")
    return v


def _check_lng(v: Optional[Decimal]) -> Optional[Decimal]:
    if v is None:
        return v
    if not (Decimal("-180") <= v <= Decimal("180")):
        raise ValueError("Längengrad muss zwischen -180 und 180 liegen")
    return v


class StorageLocationCreate(BaseModel):
    """Anlage über '+'. Status startet als 'draft'. Nur Bezeichnung ist Pflicht;
    Koordinaten/Adresse/Kapazität können bereits mitgegeben werden (atomare Anlage)."""

    name: str
    code: Optional[str] = None
    location_type: Optional[str] = None

    max_load_kg: Optional[Decimal] = None
    width_mm: Optional[int] = None
    depth_mm: Optional[int] = None
    height_mm: Optional[int] = None
    is_dry: Optional[bool] = None
    is_tempered: Optional[bool] = None
    is_hazmat: Optional[bool] = None
    is_blocked: Optional[bool] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    address_street: Optional[str] = None
    address_zip: Optional[str] = None
    address_city: Optional[str] = None
    address_country: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Bezeichnung ist ein Pflichtfeld")
        return v

    @field_validator("location_type")
    @classmethod
    def _type(cls, v: Optional[str]) -> Optional[str]:
        return _check_type(v)

    @field_validator("latitude")
    @classmethod
    def _lat(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _check_lat(v)

    @field_validator("longitude")
    @classmethod
    def _lng(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _check_lng(v)


class StorageLocationUpdate(BaseModel):
    status: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    location_type: Optional[str] = None

    max_load_kg: Optional[Decimal] = None
    width_mm: Optional[int] = None
    depth_mm: Optional[int] = None
    height_mm: Optional[int] = None
    is_dry: Optional[bool] = None
    is_tempered: Optional[bool] = None
    is_hazmat: Optional[bool] = None
    is_blocked: Optional[bool] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    address_street: Optional[str] = None
    address_zip: Optional[str] = None
    address_city: Optional[str] = None
    address_country: Optional[str] = None

    is_active: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def _status(cls, v: Optional[str]) -> Optional[str]:
        return _check_status(v)

    @field_validator("location_type")
    @classmethod
    def _type(cls, v: Optional[str]) -> Optional[str]:
        return _check_type(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Bezeichnung darf nicht leer sein")
        return v

    @field_validator("latitude")
    @classmethod
    def _lat(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _check_lat(v)

    @field_validator("longitude")
    @classmethod
    def _lng(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _check_lng(v)


class StorageLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    name: str
    code: Optional[str]
    location_type: Optional[str]

    max_load_kg: Optional[Decimal]
    width_mm: Optional[int]
    depth_mm: Optional[int]
    height_mm: Optional[int]
    is_dry: bool
    is_tempered: bool
    is_hazmat: bool
    is_blocked: bool

    latitude: Optional[Decimal]
    longitude: Optional[Decimal]
    address_street: Optional[str]
    address_zip: Optional[str]
    address_city: Optional[str]
    address_country: Optional[str]

    is_active: bool
    created_at: datetime
    updated_at: datetime
