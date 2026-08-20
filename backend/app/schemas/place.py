"""**Ein Ort in einer Antwort** — eine Station, überall dieselbe Form.

Der Ort taucht an drei Stellen auf: als **Ziel** eines Bewegen-Moduls, als **Halter**
einer Einzelinstanz und als **Station** in deren Kette. Alle drei beantworten dieselbe
Frage («welche Objektnummer, welcher Typ, wie heisst sie»), also tragen sie dieselbe
Form – eine zweite wäre eine zweite Art, denselben Ort zu schreiben.
"""

from typing import Optional

from pydantic import BaseModel


class PlaceRef(BaseModel):
    """Ein Halter: Objektnummer, Typ, Name.

    ``kind`` ist **abgeleitet** (``objects.resolve_object_type``) und nicht gespeichert –
    es sagt der Oberfläche nur, welches Symbol sie zeichnet. ``label`` ist der Name des
    Datensatzes, nicht seine Nummer: die steht daneben und ist klickbar.
    """

    object_id: int
    kind: str          # instance | user | organization
    label: str


class UnitPlace(BaseModel):
    """**Wo ein Stück liegt** – unmittelbarer Halter plus die Kette darüber.

    ``chain`` steht von innen nach aussen (Behälter › Regal › Werk Nord) und **enthält
    den unmittelbaren Halter als erstes Element**. Sie ist damit die vollständige Antwort;
    ``holder`` ist nur ihre erste Station, herausgezogen, weil die Liste sie meistens
    verkürzt zeigt.

    Eine leere Kette heisst **standortlos**, und das ist ein regulärer Zustand.
    """

    holder: Optional[PlaceRef] = None
    chain: list[PlaceRef] = []
