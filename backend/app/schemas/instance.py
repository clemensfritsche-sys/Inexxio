from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class InstanceLocation(BaseModel):
    """Eine Teilmenge einer Charge an einem Standort (Verteilung ohne Instanz-Teilung).
    Bei einer nicht verteilten Instanz enthält die Liste genau EINEN Eintrag. Read-only –
    die Verteilung entsteht ausschliesslich über einen Auftrag + Bewegungsschritt."""

    location_type: str
    location_id: int
    quantity: float
    location_label: Optional[str] = None   # vom Router denormalisiert


class LocationHop(BaseModel):
    """Eine Station der Standort-Kette (von innen nach aussen).

    ``location_type='address'`` markiert den abschliessenden geografischen Eintrag –
    er trägt keine Objektnummer, sondern die Anschrift."""

    location_type: str
    location_id: Optional[int] = None
    label: Optional[str] = None


class InstanceShare(BaseModel):
    """**Ein Anteil einer Instanz** – eine Menge mit einem Namen darauf.

    Eine Instanz ist eine Menge, kein Ding, und ihre Menge ist **immer vollständig
    aufgeteilt**: jeder Anteil gehört genau einem Auftrag, oder er ist frei. Genau so steht
    es in ``instances.reservations``; hier wird es nur sichtbar gemacht, statt es zu
    verstecken.

    Das ist die Zeile, die man in der Auswahl anklickt – und damit ist beantwortet, WEM man
    etwas wegnimmt (die Frage, die vorher niemand stellen konnte). ``order_object_id`` leer
    = **frei**: es gehört niemandem, es verliert niemand etwas."""

    order_object_id: Optional[int] = None
    order_name: Optional[str] = None
    reason: Optional[str] = None    # deviation | supply | return | provisioning | None
    quantity: float
    # **Welche Stücke** das sind – nicht nur wie viele (``services/units.py``).
    # Gekappt (``unit_count`` sagt, wie viele es insgesamt sind): eine 1000er-Charge soll
    # keine Liste mit 1000 Chips erzeugen.
    units: list[str] = []
    unit_count: int = 0


class InstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    article_id: int
    order_id: int
    kind: str
    quantity: float       # Bruchmenge möglich (kg/m²/m³/l) – nicht nur ganze Stück
    serial_number: Optional[str]
    quality: str          # QC-Verdikt: pending | passed | blocked (gesperrt)
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Standort-Verteilung (vom Router denormalisiert): bei EINEM Ort ein Eintrag, bei einer
    # verteilten Charge mehrere (300 @ Band A · 700 @ Band B). Summe = quantity.
    locations: list[InstanceLocation] = []

    reserved_for_order_id: Optional[int] = None
    reserved_quantity: float = 0   # mengengenau reservierte Menge (0 = frei)
    # **Die Stücke dieser Instanz mit ihren eigenen Nummern** (``services/units.py``):
    # eine Charge über 4 trägt 100000101-1 … -4. Gekappt, ``unit_count`` nennt die Zahl.
    units: list[str] = []
    unit_count: int = 0
    # **Die Aufteilung dieser Menge** – wer hält wie viel, und was ist frei. Vom Router
    # denormalisiert (``services/shares.py``); die Auswahl rendert daraus ihre Zeilen und
    # das Auftrags-/Instanz-Detail zeigt, wohin ein Anteil gewandert ist.
    shares: list[InstanceShare] = []

    # Das Modell-Attribut ``locations`` ist die rohe JSONB-Map (dict) – die Antwort trägt
    # aber die denormalisierte Liste. Beim ``model_validate`` die rohe dict/None auf ``[]``
    # normalisieren; der Router füllt danach die effektive Verteilung ein.
    @field_validator("locations", mode="before")
    @classmethod
    def _loc_list(cls, v):
        return v if isinstance(v, list) else []

    # Das Modell-Attribut ``units`` ist die rohe Lauf-Map (dict) – die Antwort trägt die
    # ausgeschriebenen Nummern. Beim ``model_validate`` die rohe dict/None auf ``[]``
    # normalisieren; der Router füllt danach die Nummern ein (wie bei ``locations``).
    @field_validator("units", mode="before")
    @classmethod
    def _unit_list(cls, v):
        return v if isinstance(v, list) else []

    # Denormalisiert vom Router
    order_object_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    location_label: Optional[str] = None
    # Physischer Standort bei Einbau (location_type == 'instance'): wo die Host-
    # Instanz tatsächlich liegt – die Komponente «wandert» mit ihr mit.
    physical_location_label: Optional[str] = None
    reserved_for_order_object_id: Optional[int] = None
    # **Standort-Kette** (nur im Detail gefüllt, nicht im Feed): Instanz → Behälter →
    # Behälter → Anschrift. Beantwortet «wo genau liegt das?» in einem Blick.
    location_path: list[LocationHop] = []
    # **Was mit diesem Stück passiert ist** – das Material-Journal (ADR 007), chronologisch
    # und unveränderlich. Nur im Detail gefüllt. Beginnt bei Alt-Instanzen mit der
    # Eröffnungsbilanz (``opening``); die Geschichte davor steht in den Aufträgen.
    history: list["MaterialMoveView"] = []


class MaterialMoveView(BaseModel):
    """Eine Journalzeile für die Anzeige: wann, was, wie viel, in welchen Topf – und wer.

    ``kind`` ist das semantische Ereignis (created | opening | taken | returned | released |
    sold | consumed | scrapped | blocked | unblocked). Dieselbe Zeile dient BEIDEN
    Verläufen: am **Instanz**-Detail ist der Chip der beteiligte Auftrag, am
    **Auftrags**-Detail die betroffene Instanz – dieselbe Geschichte, aus zwei Richtungen
    gelesen (die drei Fragen, ADR 007)."""

    at: datetime
    kind: str
    quantity: float
    quality: Optional[str] = None       # Zustand NACH dem Ereignis
    disposition: Optional[str] = None
    order_object_id: Optional[int] = None
    order_name: Optional[str] = None
    instance_object_id: Optional[int] = None
    note: Optional[str] = None


class ObjectReference(BaseModel):
    """Ein Verweis auf ein Objekt (Verwendungsnachweis) – generisch wiederverwendet,
    z. B. für die an einem Objekt lagernden Instanzen / referenzierenden Artikel."""

    kind: str          # menschenlesbare Rolle des Verweises
    ref_type: str      # order | instance | article | user
    object_id: int
    label: str
    at: datetime


class InstanceOrderRef(BaseModel):
    """Ein Auftrag, der diese Instanz angefasst hat – eine Instanz ist die Summe
    aller Prozesse, und Prozesse werden ausschliesslich durch Aufträge angestossen."""

    object_id: int       # Auftragsnummer (klickbar)
    status: str          # draft | released | completed | inactive
    name: str = "Auftrag"          # Name des Auftrags (dieselbe Ableitung wie im Feed)
    reason: Optional[str] = None   # Art des Unter-Auftrags (deviation | supply | …)
    roles: list[str]     # was der Auftrag mit der Instanz tat (z. B. Erzeugt, Datenerfassung)
    at: datetime         # Zeitpunkt (Sortierung/Anzeige)


class InstanceEmbed(BaseModel):
    """Kurzform für die Einbettung in den Auftrag (Instanzen-/Bewegungs-Panel)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    article_id: int   # welcher Position (Mehrpositionen-Auftrag) die Instanz zugehört
    kind: str
    quantity: float       # Bruchmenge möglich (kg/m²/m³/l)
    quality: str          # QC-Verdikt: pending | passed | blocked (gesperrt)
    disposition: str      # Verbleib: in_process | in_stock | consumed | sold | scrapped
    reserved_for_order_id: Optional[int] = None   # fest reserviert (scharf ab Freigabe)
    reserved_quantity: float = 0                   # mengengenau reservierte Menge
    location_type: Optional[str] = None
    location_id: Optional[int] = None
    location_label: Optional[str] = None   # vom Router denormalisiert
    physical_location_label: Optional[str] = None  # physischer Ort bei Einbau (instance-Kette)
    # **Wie viel dieser Instanz gehört DIESEM Auftrag?** – die eine Antwort
    # (``subject.held_quantity``), im Auftrags-Kontext immer gesetzt.
    #
    # Eine Instanz ist eine Menge, und ihre Menge ist auf Aufträge aufgeteilt: von einer
    # 4er-Charge können 2 diesem Auftrag gehören und 2 einer Abweichung. JEDE Aussage eines
    # Auftrags über «diese Instanz» meint darum seinen **Anteil**, nie die ganze Instanz –
    # wie viele Stück er bewegt, wie viele er verschrottet, wie viele er zeigt.
    #
    # Vorher hiess das Feld ``move_quantity`` und war NULL, sobald der Auftrag die ganze
    # Instanz hielt – also für genau einen Zweck (Bewegungs-Panel) gedacht. Das Verschrotten
    # rechnete deshalb mit ``quantity`` weiter und zerstörte aus einer Abweichung heraus die
    # GANZE Charge (Testnotizen #412/#414).
    held_quantity: float = 0
    # **Welche Stücke DIESER Auftrag hält** – die Nummern, nicht nur die Anzahl.
    units: list[str] = []
    unit_count: int = 0
    # Wie sich die Menge dieser Instanz auf die Aufträge verteilt – damit der Auftrag zeigen
    # kann, dass ein Teil gerade woanders liegt («2 Stk → Auftrag 100000456»). Dieselbe
    # Aussage wie im Instanz-Detail, nur gespiegelt.
    shares: list[InstanceShare] = []
    # **Aus wessen Anteil dieser Auftrag sein Stück genommen hat** – damit die Auswahl im
    # Entwurf beim erneuten Bearbeiten dieselbe Zeile wieder trifft, statt sie neu zu raten.
    pick_source_object_id: Optional[int] = None

    # Das Modell-Attribut ``units`` ist die rohe Lauf-Map (dict) – die Antwort trägt die
    # ausgeschriebenen Nummern. Beim ``model_validate`` die rohe dict/None auf ``[]``
    # normalisieren; der Router füllt danach die Nummern ein (wie bei ``locations``).
    @field_validator("units", mode="before")
    @classmethod
    def _unit_list(cls, v):
        return v if isinstance(v, list) else []

