from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .disposal import DisposalEmbed
from .document import DocumentEmbed
from .inspection import InspectionEmbed
from .instance import InstanceEmbed
from .movement import MovementEmbed
from .purchase_order import PurchaseEmbed
from .resource import ResourceEmbed
from .sale import SaleEmbed


class ShortfallInstance(BaseModel):
    """Eine freie, freigegebene Instanz am Lager, mit der sich eine Fehlmenge decken liesse
    («Andere Instanz wählen»)."""
    object_id: int
    quantity: float = 1   # Bruchmenge möglich (kg/m²/…)


class StepShortfall(BaseModel):
    """Ein ungedeckter Bedarf, der einen Schritt **blockiert** (Artikel + Fehlmenge).

    ``available_*`` beschreibt, ob & womit sich der Bedarf **aus vorhandenem Lagerbestand**
    decken liesse (für «Aus Lager decken» / «Andere Instanz wählen»)."""
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    available_quantity: float = 0
    available_instances: list[ShortfallInstance] = []


class OrderDeviationInfo(BaseModel):
    """Kurzinfo eines Unter-Auftrags (Abweichung ODER Nachschub) – für die Sichtbarkeit im
    Eltern-Auftrag."""
    object_id: int
    status: str
    reason: Optional[str] = None   # deviation | supply
    instance_count: int = 0
    instance_object_ids: list[int] = []
    title: Optional[str] = None


class OrderStepInfo(BaseModel):
    """Ein Schritt im Auftrag-Stepper (für die Fortschritts-Visualisierung).

    Mehr-Operationen-Routing: ``id`` (Schritt-Definition) ist der eindeutige
    Schlüssel; je Schritt ist – passend zum Typ – genau ein Ausführungs-Embed
    gesetzt, damit mehrere gleichartige Schritte unabhängig bedient werden."""

    id: int = 0
    step_type: str
    position: int
    label: str
    state: str   # done | active | blocked | locked | failed
    completed_by: Optional[str] = None   # wer hat den Schritt abgeschlossen
    completed_at: Optional[datetime] = None  # wann
    # Bei state='blocked': ungedeckte Bedarfe + laufende Nachschub-Unteraufträge (Objektnummern),
    # die diese Fehlmenge gerade decken.
    shortfall: list[StepShortfall] = []
    supply_order_object_ids: list[int] = []
    # Bei state='blocked' **ohne** Fehlmenge: das Material existiert, liegt aber noch am
    # falschen Ort – diese Bereitstellungs-Unteraufträge bringen es her (Objektnummern).
    # Zwei Gründe zu blockieren, zwei getrennte Felder: «zu wenig da» ≠ «noch nicht hier».
    provisioning_order_object_ids: list[int] = []
    # ALLE Bereitstellungen dieses Schritts (offen wie erledigt) – sie werden im Ablauf als
    # eigener Knoten an ihrer Position gezeigt. ``provisioning_stage`` sagt, wo diese Position
    # ist: **vor** der Ausführung (Ressource – die Komponente muss da sein, bevor verbaut wird)
    # oder **danach** (Beschaffung/Verkauf – die Ware kommt an bzw. geht hinaus, nachdem der
    # kaufmännische Vorgang durch ist). Die Deklaration liegt im Backend (``_STAGE_BEFORE``);
    # das Frontend platziert nur, es entscheidet nicht.
    provisionings: list[OrderDeviationInfo] = []
    provisioning_stage: str = "after"     # before | after

    # Ausführungs-Embed des konkreten Schritts (nur das zum Typ passende ist gesetzt).
    # «Beschaffung» und «Verkauf» sind – wie jeder andere Schritttyp – GENAU EIN Schritt,
    # auch bei mehreren Artikeln/Positionen: ``purchases``/``sales`` tragen dann mehrere
    # Belege (einen je Artikel/Position, gleicher ``step_id``); ``purchase``/``sale``
    # bleiben die ERSTEN (Bequemlichkeit/Rückwärtskompatibilität für den Einzel-Artikel-
    # Fall, wo beide identisch sind).
    purchase: Optional[PurchaseEmbed] = None
    purchases: list[PurchaseEmbed] = []
    sale: Optional[SaleEmbed] = None
    sales: list[SaleEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    disposal: Optional[DisposalEmbed] = None
    document: Optional[DocumentEmbed] = None

# completed wird automatisch gesetzt (alle Prozessschritte erledigt)
ALLOWED_STATUS = ("draft", "released", "inactive", "completed")

# FIX: Obergrenze für Bestellmengen – ``quantity`` war nur nach unten begrenzt; eine
# absurde Menge (z. B. 2e9) hätte bei der Freigabe versucht, ebenso viele Einzel-
# Instanzen zu erzeugen (Worker-/DB-Flut). Grosszügig über jedem realen Bedarf (~10 MA).
MAX_ORDER_QUANTITY = 100_000


def _validate_qty(v: Optional[float]) -> Optional[float]:
    """Menge > 0 und ≤ MAX. Bruchmengen (kg/m²/m³/l) sind erlaubt – ob ein Artikel nur
    GANZE Stück haben darf (Einzelteil), prüft der Router gegen die Serialisierung."""
    if v is None:
        return v
    if v <= 0:
        raise ValueError("Menge muss grösser als 0 sein")
    if v > MAX_ORDER_QUANTITY:
        raise ValueError(f"Menge darf höchstens {MAX_ORDER_QUANTITY} betragen")
    return v


def _validate_future_date(v: Optional[date]) -> Optional[date]:
    """Wunsch-Liefertermin darf nicht in der Vergangenheit liegen."""
    if v is None:
        return v
    if v < date.today():
        raise ValueError("Wunsch-Liefertermin darf nicht in der Vergangenheit liegen")
    return v


class OrderCreate(BaseModel):
    """Anlage eines Auftrags über '+'. Status startet als 'draft'.

    Anker ist IMMER **Artikel + Menge**. Was damit geschieht, ergibt sich aus dem Ablauf,
    der danach im Entwurf definiert wird: kein eigener Ablauf → Erzeugung (Artikel-Prozess);
    eigener Ablauf → Operation auf ``quantity`` Instanzen des Artikels (FIFO ab Lager,
    optional durch fixierte Instanzen ergänzt). Die Subjektart wird also abgeleitet.

    Weitere Artikel lassen sich danach jederzeit über ``POST .../lines`` ergänzen (Mehr-
    positionen-Auftrag – „Aus Lager"/„Instanz wählen" über mehrere Artikel; „Herstellen"
    ist dann nicht mehr möglich, siehe ``services/order_lines.py``)."""

    article_id: int
    quantity: float   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)
    desired_delivery_date: Optional[date] = None
    # Wiederkehrend (direkt am Auftrag, kein eigenes Objekt)
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: float) -> float:
        return _validate_qty(v)

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)


class OrderLineCreate(BaseModel):
    """Eine weitere Position zu einem **bestehenden** Auftrag hinzufügen (``POST
    .../lines``) – macht ihn (falls noch nicht) zu einem Mehrpositionen-Auftrag. Nur im
    Entwurf möglich; „Herstellen" scheidet dann aus (siehe ``services/order_lines.py``)."""

    article_id: int
    quantity: float   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: float) -> float:
        return _validate_qty(v)


class OrderLinePins(BaseModel):
    """Fixierte Instanzen EINER Position statt FIFO (analog ``OrderUpdate.instance_object_ids``
    am Einzel-Artikel-Auftrag)."""

    instance_object_ids: list[int] = []


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    article_id: Optional[int] = None
    quantity: Optional[float] = None   # ganze Stück ODER Bruchmenge (kg/m²/m³/l)
    # Vorgewählte Subjekt-Instanzen im Entwurf anpassen (Mehrfachauswahl, gleicher Artikel).
    instance_object_ids: Optional[list[int]] = None
    desired_delivery_date: Optional[date] = None
    recurrence_active: Optional[bool] = None
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: Optional[int] = None
    recurrence_anchor: Optional[date] = None
    # FIX: ``is_active`` ist kein Client-Feld mehr: ein PATCH {"is_active": false} auf einen
    # FREIGEGEBENEN Auftrag hätte ihn aus allen Sichten entfernt, OHNE seine Reservierungen
    # zu lösen (dauerhaft blockierter Bestand). Deaktivieren läuft über den Status-Fluss
    # (Entwurf → inaktiv) bzw. «Abbrechen» (Folgeauftrag) – nie über ein rohes Flag.
    expected_updated_at: Optional[datetime] = None   # Optimistic Locking (optional)

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_positive(cls, v: Optional[int]) -> Optional[int]:
        return _validate_qty(v)

    @field_validator("desired_delivery_date")
    @classmethod
    def _date_future(cls, v: Optional[date]) -> Optional[date]:
        return _validate_future_date(v)


class OrderDeviationCreate(BaseModel):
    """«Abweichungsauftrag anlegen»: optional die betroffenen Instanzen (Instanz-Ebene); ohne
    Auswahl wirkt die Abweichung auf alle Instanzen des Auftrags (Prozess-Ebene).

    ``abort_parent`` ist die EINE Entscheidung, die den früheren zweiten Knopf «Abbrechen»
    ersetzt: läuft der Ursprungsauftrag nach der Klärung weiter (Standard – er pausiert
    solange), oder ist er mit dem Anlegen **abgebrochen** (sofort inaktiv, endgültig; nur der
    Abweichungsauftrag lebt weiter)? Ein Vorgang, ein Wort, ein Symbol – der Unterschied ist
    eine Eigenschaft, kein zweiter Weg."""
    instance_object_ids: Optional[list[int]] = None
    abort_parent: bool = False


class OrderCoverStock(BaseModel):
    """«Aus Lager decken» / «Andere Instanz wählen»: die offene Subjekt-Fehlmenge eines
    blockierten Schritts aus vorhandenem Lagerbestand decken. Ohne ``instance_object_ids``
    wird FIFO aus dem freien Bestand reserviert; mit Auswahl genau diese Instanzen."""
    instance_object_ids: Optional[list[int]] = None


class OrderLineInfo(BaseModel):
    """Eine Position eines Mehrpositionen-Auftrags (``order.article_id`` ist dann NULL)."""
    id: int
    article_id: int
    article_object_id: Optional[int] = None
    article_name: Optional[str] = None
    article_unit: Optional[str] = None
    quantity: float   # Bruchmenge möglich (kg/m²/…)
    position: int


class OrderSummary(BaseModel):
    """Schlanke Auftrags-Sicht für den Feed (OHNE Prozess-Embeds).

    Der Feed braucht nur Kopf-Daten; die teuren Embeds (FIFO-Vorschau, Stichproben,
    Verlauf) werden erst im Detail (``GET /orders/{id}``) berechnet."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    article_id: Optional[int]
    quantity: Optional[float]   # Bruchmenge möglich (kg/m²/…)
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # denormalisiert (Batch-geladen, nicht je Auftrag)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_unit: Optional[str] = None
    purchase_status: Optional[str] = None   # für das Status-Badge im Feed
    recurrence_active: bool = False         # wiederkehrender Auftrag (Badge)
    recurrence_due: bool = False            # fällig (Termin − Vorlaufzeit erreicht)
    replaced_by_id: Optional[int] = None
    parent_order_id: Optional[int] = None   # gesetzt → Unter-Auftrag (Badge)
    reason: Optional[str] = None            # deviation | supply (Art des Unter-Auftrags)
    abort_into_id: Optional[int] = None     # gesetzt → «Abbruch ausstehend»


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    # Abgeleitete Subjektart (kein Modus-Flag): produce | stock | instance
    subject_role: str = "produce"
    # Aggregierte Bestandswirkung des Prozesses: increase | decrease | mixed | neutral
    stock_effect: str = "neutral"
    title: Optional[str]
    article_id: Optional[int]
    quantity: Optional[float]   # Bruchmenge möglich (kg/m²/…)
    desired_delivery_date: Optional[date]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Wiederkehrend (am Auftrag)
    recurrence_active: bool = False
    recurrence_interval_days: Optional[int] = None
    recurrence_lead_time_days: int = 0
    recurrence_anchor: Optional[date] = None
    recurring_parent_id: Optional[int] = None
    recurrence_due: bool = False

    # Denormalisierter Artikel + eingebetteter Prozess (Beschaffung/Verkauf)
    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    article_size: Optional[str] = None
    article_unit: Optional[str] = None
    article_weight_kg: Optional[Decimal] = None
    article_serialization: Optional[str] = None
    article_supplier_article_number: Optional[str] = None
    purchase: Optional[PurchaseEmbed] = None
    sale: Optional[SaleEmbed] = None
    # Positionen eines Mehrpositionen-Auftrags (leer beim gewöhnlichen Einzel-Artikel-Auftrag).
    order_lines: list[OrderLineInfo] = []
    instances: list[InstanceEmbed] = []
    inspection: Optional[InspectionEmbed] = None
    movement: Optional[MovementEmbed] = None
    resource: Optional[ResourceEmbed] = None
    disposal: Optional[DisposalEmbed] = None
    document: Optional[DocumentEmbed] = None
    steps: list[OrderStepInfo] = []
    # Ersetzen (Nachvollziehbarkeit): Nachfolger / Vorgänger (Objektnummern)
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None
    # Unter-Auftrag (parent) + Grund + Abbruch-Folgeauftrag (Objektnummern)
    parent_order_id: Optional[int] = None
    reason: Optional[str] = None   # deviation | supply | return | provisioning (gesetzt → Unter-Auftrag)
    abort_into_id: Optional[int] = None
    # Sichtbarkeit der Unteraufträge im Eltern-Auftrag + Pause-Zustand
    deviations: list[OrderDeviationInfo] = []        # Abweichungen (pausieren den Eltern)
    supply_orders: list[OrderDeviationInfo] = []     # Nachschub (deckt Bedarf; blockiert nur Schritte)
    returns: list[OrderDeviationInfo] = []           # Retouren/Erstattungen (pausieren NICHT)
    # Bereitstellungen: bringen vorhandenes Material an den Ort, den ein Schritt verlangt
    # (blockiert nur den betroffenen Schritt, pausiert den Eltern NICHT). Eigener Topf, weil
    # eine Bereitstellung sonst im ``deviations``-Topf landete und als «Abweichung» erschiene.
    provisionings: list[OrderDeviationInfo] = []
    paused: bool = False   # pausiert, weil eine Abweichung offen / ein Abbruch ausstehend ist
