"""Zahlungs-Bridge – ein Interface, hinter dem **manual** (Default, überbrückbar für
Tests) und **stripe** (Gerüst) liegen. So bleibt der Checkout provider-agnostisch.

``create_checkout`` liefert eine URL, auf die der Kunde zum Bezahlen umgeleitet wird;
``handle_event`` verarbeitet die Rückmeldung des Providers (Zahlung erfolgreich/abgebrochen)
und setzt den Verkaufs-Status.
"""

from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from ...models import Order, Sale


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_checkout(self, db: Session, order: Order, sale: Sale) -> str:
        """Eine Zahl-URL für diesen Verkauf erzeugen (Redirect-Ziel des Kunden)."""

    @abstractmethod
    def handle_event(self, db: Session, payload: dict) -> Sale | None:
        """Provider-Ereignis verarbeiten (Zahlung bestätigt/abgebrochen). Setzt den
        Verkaufs-Status und stösst den Auftrag an. Liefert den betroffenen Verkauf."""
