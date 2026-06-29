"""Schemas für die **Verkaufs-Ebene am Artikel** (ERP-Sicht): Profil (Publiziert/
Sichtbarkeit/Inhalt), Preise (1:n) und Zielgruppe (private/unlisted)."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

PRICE_KINDS = ("one_time", "subscription")
INTERVALS = ("month", "year")
TAX_CLASSES = ("standard", "reduced", "lodging", "zero")
VISIBILITIES = ("public", "private", "unlisted")


# ─── Preis (Anzeige-View aus der Pipeline) ───────────────────────────────────────

class PriceView(BaseModel):
    """Berechneter Anzeige-Preis (eine Währung) – Ergebnis der Preis-Pipeline."""
    currency: str
    kind: str = "one_time"
    interval: Optional[str] = None
    net: Decimal
    compare_at: Optional[Decimal] = None
    tax_rate: Decimal           # MWST-Satz in Prozent (z. B. 8.1)
    gross: Decimal


# ─── Preis (Pflege) ──────────────────────────────────────────────────────────────

class ArticlePriceBase(BaseModel):
    kind: str = "one_time"
    interval: Optional[str] = None
    amount_chf: Decimal
    compare_at_chf: Optional[Decimal] = None
    tax_class: str = "standard"
    is_primary: bool = False

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in PRICE_KINDS:
            raise ValueError(f"Art muss eine von {', '.join(PRICE_KINDS)} sein")
        return v

    @field_validator("interval")
    @classmethod
    def _interval_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in INTERVALS:
            raise ValueError(f"Intervall muss eine von {', '.join(INTERVALS)} sein")
        return v

    @field_validator("tax_class")
    @classmethod
    def _tax_ok(cls, v: str) -> str:
        if v not in TAX_CLASSES:
            raise ValueError(f"Steuerklasse muss eine von {', '.join(TAX_CLASSES)} sein")
        return v

    @field_validator("amount_chf")
    @classmethod
    def _amount_pos(cls, v: Decimal) -> Decimal:
        if v is None or v <= 0:
            raise ValueError("Betrag muss grösser als 0 sein")
        return v


class ArticlePriceCreate(ArticlePriceBase):
    pass


class ArticlePriceUpdate(BaseModel):
    kind: Optional[str] = None
    interval: Optional[str] = None
    amount_chf: Optional[Decimal] = None
    compare_at_chf: Optional[Decimal] = None
    tax_class: Optional[str] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PRICE_KINDS:
            raise ValueError(f"Art muss eine von {', '.join(PRICE_KINDS)} sein")
        return v

    @field_validator("interval")
    @classmethod
    def _interval_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in INTERVALS:
            raise ValueError(f"Intervall muss eine von {', '.join(INTERVALS)} sein")
        return v

    @field_validator("tax_class")
    @classmethod
    def _tax_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TAX_CLASSES:
            raise ValueError(f"Steuerklasse muss eine von {', '.join(TAX_CLASSES)} sein")
        return v

    @field_validator("amount_chf")
    @classmethod
    def _amount_pos(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Betrag muss grösser als 0 sein")
        return v


class ArticlePriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: int
    kind: str
    interval: Optional[str] = None
    amount_chf: Decimal
    compare_at_chf: Optional[Decimal] = None
    tax_class: str
    is_primary: bool
    is_active: bool


# ─── Zielgruppe (private/unlisted) ───────────────────────────────────────────────

class AudienceMember(BaseModel):
    id: int            # Zeilen-id der Zuordnung
    user_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    object_id: Optional[int] = None


class AudienceAdd(BaseModel):
    user_id: int


# ─── Profil ──────────────────────────────────────────────────────────────────────

class ArticleSalesUpdate(BaseModel):
    sales_published: Optional[bool] = None
    sales_visibility: Optional[str] = None
    sales_content: Optional[dict] = None

    @field_validator("sales_visibility")
    @classmethod
    def _vis_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VISIBILITIES:
            raise ValueError(f"Sichtbarkeit muss eine von {', '.join(VISIBILITIES)} sein")
        return v


class ArticleSalesProfile(BaseModel):
    """Vollständige Verkaufs-Ebene eines Artikels (ERP-Reiter «Verkauf»)."""
    object_id: Optional[int] = None
    status: str
    sales_published: bool
    sales_visibility: str
    sales_content: Optional[dict] = None
    prices: list[ArticlePriceResponse] = []
    audience: list[AudienceMember] = []
    # Live-Vorschau des berechneten Preises je Shop-Währung (CHF/EUR/USD …)
    previews: list[PriceView] = []
