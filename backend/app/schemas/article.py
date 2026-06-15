import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# ─── Erlaubte Werte ──────────────────────────────────────────────────────────

ALLOWED_UNITS = ("Stk", "mm", "m2", "kg", "l")
ALLOWED_SERIALIZATION = ("unit", "batch")
ALLOWED_STATUS = ("draft", "released", "inactive")

_SIZE_RE = re.compile(r"^\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)+$")


# ─── Wiederverwendbare Validatoren ───────────────────────────────────────────

def normalize_size(raw: str) -> str:
    """Validiere & normalisiere eine Grössenangabe.

    Regeln: Zahlen getrennt durch 'x', jeweils > 0, aufsteigend (klein → gross),
    z. B. ``3x40x600``. ``×`` und ``X`` werden zu ``x`` normalisiert.
    """
    s = raw.strip().lower().replace("×", "x").replace(" ", "")
    if not _SIZE_RE.match(s):
        raise ValueError(
            "Grösse muss aus Zahlen bestehen, getrennt durch 'x' (z. B. 3x40x600)"
        )
    parts = [float(p) for p in s.split("x")]
    if any(p <= 0 for p in parts):
        raise ValueError("Alle Masse müssen grösser als 0 sein")
    if any(parts[i] > parts[i + 1] for i in range(len(parts) - 1)):
        raise ValueError("Masse müssen aufsteigend angegeben werden (klein → gross)")
    return s


def validate_weight(value: Decimal) -> Decimal:
    """Gewicht: grösser als 0, höchstens 3 Nachkommastellen."""
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Gewicht muss eine Zahl sein")
    if d <= 0:
        raise ValueError("Gewicht darf nicht 0 sein und muss grösser als 0 sein")
    if d.as_tuple().exponent < -3:
        raise ValueError("Gewicht darf höchstens 3 Nachkommastellen haben")
    return d


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    """Anlage eines Artikels über den '+'-Button. Status startet immer als 'draft'."""

    name: str
    unit: str
    serialization: str
    size: str
    weight_kg: Decimal

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Name ist ein Pflichtfeld")
        return v

    @field_validator("unit")
    @classmethod
    def _unit_allowed(cls, v: str) -> str:
        if v not in ALLOWED_UNITS:
            raise ValueError(f"Einheit muss eine von {', '.join(ALLOWED_UNITS)} sein")
        return v

    @field_validator("serialization")
    @classmethod
    def _serialization_allowed(cls, v: str) -> str:
        if v not in ALLOWED_SERIALIZATION:
            raise ValueError("Seriennummererfassung muss 'unit' (Einzelteil) oder 'batch' sein")
        return v

    @field_validator("size")
    @classmethod
    def _size_valid(cls, v: str) -> str:
        return normalize_size(v)

    @field_validator("weight_kg")
    @classmethod
    def _weight_valid(cls, v: Decimal) -> Decimal:
        return validate_weight(v)


class ArticleUpdate(BaseModel):
    """Teil-Update aus dem Detailfenster. Alle Felder optional."""

    status: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    serialization: Optional[str] = None
    size: Optional[str] = None
    weight_kg: Optional[Decimal] = None
    is_active: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name darf nicht leer sein")
        return v

    @field_validator("unit")
    @classmethod
    def _unit_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_UNITS:
            raise ValueError(f"Einheit muss eine von {', '.join(ALLOWED_UNITS)} sein")
        return v

    @field_validator("serialization")
    @classmethod
    def _serialization_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_SERIALIZATION:
            raise ValueError("Seriennummererfassung muss 'unit' (Einzelteil) oder 'batch' sein")
        return v

    @field_validator("size")
    @classmethod
    def _size_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_size(v)

    @field_validator("weight_kg")
    @classmethod
    def _weight_valid(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        return validate_weight(v)


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    name: str
    unit: str
    serialization: str
    size: str
    weight_kg: Decimal
    landed_unit_cost: Optional[Decimal] = None  # read-only, aus Bestellung
    is_active: bool
    created_at: datetime
    updated_at: datetime
