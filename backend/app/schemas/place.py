"""Der **Ort** (`place`) – ein Standort als Adresse/GPS, den eine Instanz DIREKT trägt.

Kernidee des Standort-Modells: **ein Standort ist ein Halter.** Es gibt genau vier Arten,
und nur eine davon ist kein Datensatzobjekt:

    place    → Adresse/GPS **inline** auf der Instanz (KEINE Objektnummer) ← das «Blatt»
    user     → UserProfile (Mitarbeiter, Lieferant, Kunde)      – Objektnummer
    instance → andere Instanz (Behälter, Palette, Maschine, LKW) – Objektnummer
    company  → das Unternehmen selbst (Betriebsadresse)          – Objektnummer

Ein **benannter Platz** (Regal A, Wareneingang, LKW 1) ist damit einfach eine **Instanz**,
die andere Instanzen hält – kein Sondertyp, kein eigener Datensatztyp. Genau das ersetzt
den früheren `lagerplatz`.

**Form = Versand-Adress-Snapshot.** Die Feldnamen sind bewusst identisch mit den
Adress-Snapshots der Sendungen (`services/logistics.py`: `same_place`, `_addr_label`,
`_has_address`), damit Klassifikation, Adressvergleich und Etikett-Rendering den Ort OHNE
Übersetzung verarbeiten – eine Form, eine Wahrheit.
"""

from typing import Optional

from pydantic import BaseModel, model_validator


class Place(BaseModel):
    """Ein Ort: freie Bezeichnung + Adresse + optionale Koordinaten.

    Mindestens EINE inhaltliche Angabe ist Pflicht – ein leerer Ort wäre bedeutungslos
    (dann ist der Standort schlicht ``NULL`` = «noch nicht festgelegt»)."""

    name: Optional[str] = None       # freie Bezeichnung («Baustelle Müller», «Aussenlager»)
    street1: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    country: str = "CH"
    lat: Optional[float] = None
    lng: Optional[float] = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not any([
            (self.name or "").strip(), (self.street1 or "").strip(),
            (self.zip or "").strip(), (self.city or "").strip(),
            self.lat is not None and self.lng is not None,
        ]):
            raise ValueError("Ort braucht mindestens eine Bezeichnung, Adresse oder Koordinaten")
        return self

    def as_dict(self) -> dict:
        """Persistenz-/Snapshot-Form (leere Felder weglassen – schlanker JSONB)."""
        raw = {
            "name": (self.name or "").strip() or None,
            "street1": (self.street1 or "").strip() or None,
            "zip": (self.zip or "").strip() or None,
            "city": (self.city or "").strip() or None,
            "country": (self.country or "CH").strip() or "CH",
            "lat": self.lat,
            "lng": self.lng,
        }
        return {k: v for k, v in raw.items() if v is not None}
