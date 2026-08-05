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


class InstanceUnit(BaseModel):
    """**Ein einzelnes Stück** – die EINE Form, in der ein Teil überall genannt wird.

    Drei Angaben, immer und überall dieselben (Testnotizen #531/#532):

        number      die Objektnummer **inklusive Zusatz** – ``100000623-1``
        quantity    seine Menge (fast immer 1; eine nicht zählbare Charge trägt hier 2.5)
        Zustand     ``quality`` + ``disposition`` + ob es gerade jemand hält

    Der Zustand steht als die beiden Instanz-Achsen da (nicht als fertiges Wort), damit ihn
    jede Ansicht mit **derselben** Projektion auf eine Ampelfarbe bringt wie überall sonst
    (``lib/process.instanceStatusConfig``) – kein zweites Regelwerk, keine zweite Wahrheit.

    Der **Halter** ist der Auftrag, der das Stück beansprucht (leer = frei): er entscheidet,
    ob der Zustand «gebunden» ist, und macht die Zeile anklickbar."""

    number: str
    quantity: float
    quality: str          # pending | passed | blocked
    disposition: str      # in_process | in_stock | consumed | sold | scrapped
    # **Wo dieses Stück liegt** (Testnotiz #605) – dieselbe Angabe für eine Charge wie für
    # ein Einzelteil, EINE Logik: die Standort-Verteilung der Instanz wird der Reihe nach
    # auf ihre lebenden Stücke verteilt (bei EINEM Ort bekommt sie jedes Stück). Ein
    # ausgeschiedenes Stück hat keinen Standort mehr – sein Endzustand IST die Wo-Aussage.
    location_label: Optional[str] = None
    location_object_id: Optional[int] = None
    # **Seit wann dieses Stück am Lager ist** – die FIFO-Basis, am Stück statt an der
    # Instanz (``services/units.py``). Gesetzt beim ERSTEN Freigeben und danach nie mehr
    # angefasst; eine Retoure setzt sie nicht zurück. Leer = noch nicht freigegeben.
    in_stock_since: Optional[datetime] = None
    order_object_id: Optional[int] = None
    order_name: Optional[str] = None
    reason: Optional[str] = None   # deviation | supply | return | provisioning | None


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
    units: list[InstanceUnit] = []
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
    # **Was hier entnehmbar ist – die EINE Zahl** (``inventory.ready_qty``, Testnotiz #647):
    # frei UND freigegeben UND nicht gesperrt, **je Stück** gezählt. Genau das, was die
    # FIFO-Allokation nehmen könnte. Sie steht hier, weil eine Oberfläche sie sonst aus den
    # Skalaren nachbaut («quality==passed && disposition==in_stock && nicht reserviert») –
    # und das ist eine Aussage über den **Datensatz**, nicht über die Menge: eine Charge à
    # 500, von der EIN Stück reserviert ist, galt damit als vollständig belegt.
    available_quantity: float = 0
    # **Die Stücke dieser Instanz mit ihren eigenen Nummern** (``services/units.py``):
    # eine Charge über 4 trägt 100000101-1 … -4. Gekappt, ``unit_count`` nennt die Zahl.
    units: list[InstanceUnit] = []
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
    # Die Mengeneinheit des Artikels – eine Menge ohne Einheit ist eine halbe Auskunft
    # («2.5» wovon?). Denormalisiert vom Router aus derselben Batch-Abfrage.
    article_unit: Optional[str] = None
    location_label: Optional[str] = None
    # Physischer Standort bei Einbau (location_type == 'instance'): wo die Host-
    # Instanz tatsächlich liegt – die Komponente «wandert» mit ihr mit.
    physical_location_label: Optional[str] = None
    reserved_for_order_object_id: Optional[int] = None
    # **Standort-Kette** (nur im Detail gefüllt, nicht im Feed): Instanz → Behälter →
    # Behälter → Anschrift. Beantwortet «wo genau liegt das?» in einem Blick.
    location_path: list[LocationHop] = []
    # **Kein Journal in der Antwort** (Testnotizen #628/#629): das Material-Journal bleibt
    # die Wahrheit über die Vergangenheit (ADR 007) und speist Fluss-Kanten, Stück-Zustände
    # und das Systemprotokoll – als *Liste von Buchungen* am Datensatz sagte es dagegen
    # nichts, was der Fluss und die Stücke nicht schon zeigen. Wer die Mechanik sehen will,
    # öffnet das Systemprotokoll; dort steht sie mit Audit und Ereignissen zusammen.


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
    units: list[InstanceUnit] = []
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

