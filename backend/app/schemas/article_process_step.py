from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..services.article_fields import normalize_shared_fields

ALLOWED_STEP_TYPES = ("purchase", "serialization", "inspection")
ALLOWED_MODES = ("supplier", "webshop")


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

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> list[str]:
        return normalize_shared_fields(v)

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
        return self


class ArticleProcessStepUpdate(BaseModel):
    """Teil-Update eines Prozessschritts."""

    position: Optional[int] = None
    mode: Optional[str] = None
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    sample_percent: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        return normalize_shared_fields(v)

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
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("shared_fields", mode="before")
    @classmethod
    def _shared_default(cls, v: Optional[list]) -> list[str]:
        return normalize_shared_fields(v)
