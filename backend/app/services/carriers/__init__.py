"""**Welche Frachtführer einsatzbereit sind — und keiner mehr** (SYSTEM_LOGIC K4).

Kein «aktiver Anbieter» und **kein Rückfall**. Der Vorgänger wählte einen aus (Sendcloud
≻ Shippo ≻ manual) und fiel stillschweigend auf «manual» zurück, wenn nichts konfiguriert
war – «nie kaputt», und genau darum merkte niemand, dass nie ein Tarif kam.

Hier gilt stattdessen: **jeder konfigurierte Anbieter wird gefragt**, und seine Angebote
stehen nebeneinander in derselben Liste. Das ist nicht bloss ehrlicher, es ist die
Fachaussage: eine Ausschreibung fragt mehrere. Ist keiner konfiguriert, gibt es den Kanal
`plattform` **nicht** – er ist dann nicht wählbar, statt zu erscheinen und zu scheitern.

Ein neuer Anbieter ist **eine Zeile in ``_CARRIERS``** und eine Datei daneben. Es gibt
keine Fallunterscheidung nach dem Anbieter in der Fachlogik – der Adapter **ist** sie.
"""

from .base import (
    Address, Carrier, CarrierOffer, UNZUSTELLBAR, Label, Parcel, Quote, Tracking,
    UNTERWEGS, ZUGESTELLT,
)
from .sendcloud import Sendcloud
from .shippo import Shippo

#: Alle bekannten Anbieter. Reihenfolge = Reihenfolge der Anfrage; sortiert wird das
#: Ergebnis ohnehin nach Preis (``awards.offers``).
_CARRIERS: tuple[type[Carrier], ...] = (Sendcloud, Shippo)

__all__ = [
    "Address", "Carrier", "CarrierOffer", "Label", "Parcel", "Quote", "Tracking",
    "UNTERWEGS", "ZUGESTELLT", "UNZUSTELLBAR", "active", "by_key", "available",
]


def active() -> list[Carrier]:
    """Die **einsatzbereiten** Anbieter – die mit Schlüssel."""
    return [c() for c in _CARRIERS if c().available()]


def available() -> bool:
    """Gibt es den Kanal «Plattform» überhaupt? Sonst ist er nicht wählbar."""
    return bool(active())


def by_key(key: str) -> Carrier:
    """Ein bestimmter Anbieter – zum Kaufen und Nachverfolgen.

    Unbekannt oder nicht konfiguriert ist ein **Fehler**, kein Rückfall: ein Etikett bei
    einem anderen als dem gewählten Frachtführer zu kaufen wäre eine stille Ersatzwahl.
    """
    from fastapi import HTTPException

    for c in _CARRIERS:
        if c.key == key:
            found = c()
            if not found.available():
                raise HTTPException(
                    status_code=409,
                    detail=(f"«{found.label}» ist nicht eingerichtet – ohne Schlüssel "
                            f"kann dort weder gekauft noch nachverfolgt werden."),
                )
            return found
    raise HTTPException(400, f"«{key}» ist kein bekannter Frachtführer.")
