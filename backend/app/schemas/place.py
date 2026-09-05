"""**Ein Ort in einer Antwort** — eine Station, überall dieselbe Form.

Der Ort taucht an drei Stellen auf: als **Ziel** eines Bewegen-Moduls, als **Halter**
einer Einzelinstanz und als **Station** in deren Kette. Alle drei beantworten dieselbe
Frage («welche Objektnummer, welcher Typ, wie heisst sie»), also tragen sie dieselbe
Form – eine zweite wäre eine zweite Art, denselben Ort zu schreiben.
"""

from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - nur für die Typprüfung
    from ..services.places import Station


class PlaceRef(BaseModel):
    """Ein Halter: Objektnummer, Typ, Name.

    ``kind`` ist **abgeleitet** (``objects.resolve_object_type``) und nicht gespeichert –
    es sagt der Oberfläche nur, welches Symbol sie zeichnet. ``label`` ist der Name des
    Datensatzes, nicht seine Nummer: die steht daneben und ist klickbar.
    """

    object_id: int
    kind: str          # instance | user | organization | unit
    label: str
    #: **Die Stück-Nummer**, wenn der Halter ein *Träger* ist (``100000123-3``). Ein Stück
    #: hat keinen eigenen Datensatz, aber einen eindeutigen Namen; ``object_id`` führt
    #: dann auf seine **Instanz**. Die Anzeige zieht diese Nummer vor, weil sie die
    #: genauere Aussage ist.
    number: Optional[str] = None

    @classmethod
    def of(cls, station: "Station | None") -> "Optional[PlaceRef]":
        """Station → Antwortform. **Die eine Umwandlung** – drei Aufrufstellen teilen sie.

        Ein Halter, den es nicht mehr gibt (``None``), bleibt ``None``: die Anzeige zeigt
        dann nichts statt eines Namens, den sie nicht kennt – tolerant lesen, streng
        schreiben.
        """
        return cls(object_id=station.object_id, kind=station.kind,
                   label=station.label, number=station.number) if station else None


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
