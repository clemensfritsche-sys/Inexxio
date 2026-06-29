"""Schemas für den öffentlichen Shop (Kunde): Produkt-Listing/-Detail, Checkout,
Zahlungs-Simulation."""

from typing import Optional

from pydantic import BaseModel, field_validator

from .sales import PriceView


class ShopProduct(BaseModel):
    """Ein publiziertes Produkt im Shop (lokalisierter Inhalt + berechneter Preis)."""
    object_id: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    images: list[str] = []
    visibility: str = "public"
    fulfillment: str = "make"   # make = auf Bestellung gefertigt | stock = ab Lager
    unit: Optional[str] = None
    price: Optional[PriceView] = None


class ShopCheckout(BaseModel):
    article_object_id: int
    quantity: int = 1
    currency: str = "CHF"

    @field_validator("quantity")
    @classmethod
    def _qty_pos(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v


class ShopCheckoutResult(BaseModel):
    order_object_id: int
    sale_token: str
    provider: str
    payment_url: str


class PaymentSimulate(BaseModel):
    sale_token: str
    result: str = "paid"   # paid | cancelled
