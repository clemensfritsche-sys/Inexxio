from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..services.article_fields import normalize_shared_fields

ALLOWED_STEP_TYPES = ("purchase",)
ALLOWED_MODES = ("supplier", "webshop")


def _clean_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    return v.strip() or None


class ArticleProcessStepCreate(BaseModel):
    """Anlage eines Prozessschritts im Reiter «Prozess» des Artikels."""

    step_type: str = "purchase"
    mode: str = "supplier"
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None

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

    @model_validator(mode="after")
    def _mode_consistent(self) -> "ArticleProcessStepCreate":
        if self.mode == "supplier" and not self.supplier_id:
            raise ValueError("Im Modus 'Lieferant' muss ein Lieferant gewählt sein")
        if self.mode == "webshop" and not self.webshop_url:
            raise ValueError("Im Modus 'Webshop' muss ein Link hinterlegt sein")
        return self


class ArticleProcessStepUpdate(BaseModel):
    """Teil-Update eines Prozessschritts."""

    mode: Optional[str] = None
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    position: Optional[int] = None
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
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("shared_fields", mode="before")
    @classmethod
    def _shared_default(cls, v: Optional[list]) -> list[str]:
        return normalize_shared_fields(v)
