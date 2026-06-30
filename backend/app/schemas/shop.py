"""Schemas für den öffentlichen Shop (Kunde): Produkt-Listing/-Detail, Warenkorb-Checkout,
Zahlungs-Simulation."""

from typing import Optional

from pydantic import BaseModel, field_validator

from .sales import PriceView


class ShopPriceOption(BaseModel):
    """Eine **wählbare Preis-Option** eines Produkts (mehrere je Artikel möglich):
    Einmalkauf, Nutzungsabo, Produktabo … – der Kunde wählt eine im Shop."""
    price_id: int
    kind: str = "one_time"               # one_time | subscription
    interval: Optional[str] = None       # month | year (nur Abo)
    sub_type: Optional[str] = None       # usage | product (nur Abo)
    is_primary: bool = False
    view: PriceView


class ShopProduct(BaseModel):
    """Ein publiziertes Produkt im Shop (lokalisierter Inhalt + Preis-Optionen)."""
    object_id: int
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    images: list[str] = []
    visibility: str = "public"
    fulfillment: str = "make"   # make = auf Bestellung gefertigt | stock = ab Lager
    unit: Optional[str] = None
    # Hauptpreis (für die Listing-Kachel) + alle wählbaren Optionen (Detail/Warenkorb).
    price: Optional[PriceView] = None
    prices: list[ShopPriceOption] = []


class ShopCheckoutItem(BaseModel):
    """Eine Warenkorb-Position: konkretes Produkt + gewählte Preis-Option + Menge."""
    article_object_id: int
    price_id: Optional[int] = None       # gewählte Option; None = Hauptpreis
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def _qty_pos(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v


class ShopCheckout(BaseModel):
    """Warenkorb-Checkout: eine oder mehrere Positionen ⇒ eine Zahlungs-Session."""
    items: list[ShopCheckoutItem]

    @field_validator("items")
    @classmethod
    def _items_nonempty(cls, v: list) -> list:
        if not v:
            raise ValueError("Der Warenkorb ist leer")
        return v


class ShopCheckoutResult(BaseModel):
    """Ergebnis des Checkouts. Embedded (Stripe): ``client_secret`` + ``session_id``
    füllen das eingebettete Kassen-Widget. Manual (Fallback): ``payment_url`` (Redirect
    auf die interne Test-Seite). ``token`` referenziert den CheckoutIntent."""
    token: str
    provider: str
    session_id: Optional[str] = None
    client_secret: Optional[str] = None
    payment_url: Optional[str] = None


class PaymentSimulate(BaseModel):
    sale_token: str
    result: str = "paid"   # paid | cancelled
