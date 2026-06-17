from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..services.article_fields import normalize_shared_fields
from .movement import LOCATION_TYPES

ALLOWED_STEP_TYPES = ("purchase", "serialization", "inspection", "movement")
ALLOWED_MODES = ("supplier", "webshop")
ALLOWED_CAPTURE_TYPES = ("measure", "bool", "text")


def _check_target_location_type(v: Optional[str]) -> Optional[str]:
    """Vorgabe-Zieltyp der Bewegung (leer = Lagerist entscheidet frei)."""
    if v is None or v == "":
        return None
    if v not in LOCATION_TYPES:
        raise ValueError(f"Zieltyp muss eine von {', '.join(LOCATION_TYPES)} sein")
    return v


class CaptureField(BaseModel):
    """Ein Erfassungsfeld der Datenerfassung (Prozessschritt «inspection»)."""

    key: str = ""
    label: str
    type: str = "measure"            # measure (Soll-Ist) | bool (Gut/Schlecht) | text
    target: Optional[float] = None   # Sollwert (measure)
    tolerance: Optional[float] = None  # ± Toleranz (measure)
    unit: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ALLOWED_CAPTURE_TYPES:
            raise ValueError("Feldtyp muss measure, bool oder text sein")
        return v

    @field_validator("label")
    @classmethod
    def _label_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Bezeichnung des Erfassungsfelds fehlt")
        return v


def normalize_capture_fields(fields: Optional[list]) -> list[dict]:
    """Erfassungsfelder validieren, Keys vergeben/eindeutig machen."""
    out: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(fields or []):
        cf = raw if isinstance(raw, CaptureField) else CaptureField(**raw)
        key = (cf.key or "").strip() or f"feld_{i + 1}"
        while key in seen:
            key = f"{key}_{i + 1}"
        seen.add(key)
        d = cf.model_dump()
        d["key"] = key
        if cf.type != "measure":
            d["target"] = None
            d["tolerance"] = None
        out.append(d)
    return out


def _clean_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    return v.strip() or None


def _check_percent(v: Optional[int]) -> Optional[int]:
    if v is None:
        return v
    if not (1 <= v <= 100):
        raise ValueError("Prüfumfang muss zwischen 1 und 100 % liegen")
    return v


class ArticleProcessStepCreate(BaseModel):
    """Anlage eines Prozessschritts im Reiter «Prozess» des Artikels."""

    step_type: str = "purchase"
    position: Optional[int] = None
    mode: str = "supplier"
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    sample_percent: Optional[int] = None
    capture_fields: Optional[list[CaptureField]] = None
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> list[str]:
        return normalize_shared_fields(v)

    @field_validator("target_location_type")
    @classmethod
    def _target_type_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_target_location_type(v)

    @field_validator("step_type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ALLOWED_STEP_TYPES:
            raise ValueError(f"Schritt-Typ muss eine von {', '.join(ALLOWED_STEP_TYPES)} sein")
        return v

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ALLOWED_MODES:
            raise ValueError("Modus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("webshop_url")
    @classmethod
    def _url_clean(cls, v: Optional[str]) -> Optional[str]:
        return _clean_url(v)

    @field_validator("sample_percent")
    @classmethod
    def _pct_ok(cls, v: Optional[int]) -> Optional[int]:
        return _check_percent(v)

    @model_validator(mode="after")
    def _consistent(self) -> "ArticleProcessStepCreate":
        # Bezugsquelle nur beim Beschaffungsschritt relevant
        if self.step_type == "purchase":
            if self.mode == "supplier" and not self.supplier_id:
                raise ValueError("Im Modus 'Lieferant' muss ein Lieferant gewählt sein")
            if self.mode == "webshop" and not self.webshop_url:
                raise ValueError("Im Modus 'Webshop' muss ein Link hinterlegt sein")
        if self.step_type == "inspection" and self.sample_percent is None:
            self.sample_percent = 100  # Default: ganze Menge prüfen
        if self.step_type == "movement":
            # Ohne Zieltyp gibt es kein festes Zielobjekt
            if self.target_location_type is None:
                self.target_location_id = None
        return self


class ArticleProcessStepUpdate(BaseModel):
    """Teil-Update eines Prozessschritts."""

    position: Optional[int] = None
    mode: Optional[str] = None
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    sample_percent: Optional[int] = None
    capture_fields: Optional[list[CaptureField]] = None
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        return normalize_shared_fields(v)

    @field_validator("target_location_type")
    @classmethod
    def _target_type_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_target_location_type(v)

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_MODES:
            raise ValueError("Modus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("webshop_url")
    @classmethod
    def _url_clean(cls, v: Optional[str]) -> Optional[str]:
        return _clean_url(v)

    @field_validator("sample_percent")
    @classmethod
    def _pct_ok(cls, v: Optional[int]) -> Optional[int]:
        return _check_percent(v)


class ArticleProcessStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    position: int
    step_type: str
    mode: str
    supplier_id: Optional[int]
    supplier_name: Optional[str] = None  # vom Router denormalisiert
    webshop_url: Optional[str]
    shared_fields: list[str] = []
    sample_percent: Optional[int] = None
    capture_fields: list[CaptureField] = []
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("shared_fields", mode="before")
    @classmethod
    def _shared_default(cls, v: Optional[list]) -> list[str]:
        return normalize_shared_fields(v)

    @field_validator("capture_fields", mode="before")
    @classmethod
    def _capture_default(cls, v: Optional[list]) -> list:
        return v or []
