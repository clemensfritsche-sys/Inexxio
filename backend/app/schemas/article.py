import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# ─── Erlaubte Werte ──────────────────────────────────────────────────────────

ALLOWED_UNITS = ("Stk", "mm", "m2", "m3", "kg", "l")
ALLOWED_SERIALIZATION = ("unit", "batch")
ALLOWED_STATUS = ("draft", "released", "inactive")
# Beschaffungsquelle (Teil der Spezifikation): Lieferant ODER Webshop-Link.
ALLOWED_PROCUREMENT_MODES = ("supplier", "webshop")


def _clean_webshop_url(v: Optional[str]) -> Optional[str]:
    """Webshop-Link säubern + auf ein gültiges http(s)-URL prüfen (leer → None)."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        raise ValueError("Bitte einen gültigen Link angeben (z. B. https://shop.example.com/…)")
    return v

# Artikelnamen sind frei wählbar, aber bewusst KURZ gehalten (Feed/Etiketten/Listen bleiben
# lesbar). Der Wert wird zentral hier gekappt – das Frontend begrenzt die Eingabe zusätzlich.
NAME_MAX_LENGTH = 32

_SIZE_RE = re.compile(r"^\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)+$")


def clean_article_name(v: Optional[str], *, required: bool = True) -> Optional[str]:
    """Artikelname normalisieren: trimmen, auf ``NAME_MAX_LENGTH`` kappen. ``required`` steuert,
    ob ein leerer Wert ein Fehler ist (Anlage) oder erlaubt bleibt (None-Teilupdate)."""
    if v is None:
        if required:
            raise ValueError("Name ist ein Pflichtfeld")
        return None
    v = v.strip()
    if not v:
        raise ValueError("Name ist ein Pflichtfeld" if required else "Name darf nicht leer sein")
    return v[:NAME_MAX_LENGTH].rstrip()


# ─── Wiederverwendbare Validatoren ───────────────────────────────────────────

def normalize_size(raw: str) -> str:
    """Validiere & normalisiere eine Grössenangabe.

    Regeln: Zahlen getrennt durch 'x', jeweils > 0, aufsteigend (klein → gross),
    z. B. ``3x40x600``. ``×`` und ``X`` werden zu ``x`` normalisiert.
    """
    s = raw.strip().lower().replace("×", "x").replace(" ", "")
    if not _SIZE_RE.match(s):
        raise ValueError(
            "Grösse muss aus Zahlen bestehen, getrennt durch 'x' (z. B. 3x40x600)"
        )
    parts = [float(p) for p in s.split("x")]
    if any(p <= 0 for p in parts):
        raise ValueError("Alle Masse müssen grösser als 0 sein")
    if any(parts[i] > parts[i + 1] for i in range(len(parts) - 1)):
        raise ValueError("Masse müssen aufsteigend angegeben werden (klein → gross)")
    return s


def validate_weight(value: Decimal) -> Decimal:
    """Gewicht: grösser als 0, höchstens 3 Nachkommastellen."""
    try:
        d = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Gewicht muss eine Zahl sein")
    if d <= 0:
        raise ValueError("Gewicht darf nicht 0 sein und muss grösser als 0 sein")
    if d.as_tuple().exponent < -3:
        raise ValueError("Gewicht darf höchstens 3 Nachkommastellen haben")
    return d


def _opt_text(v: Optional[str]) -> Optional[str]:
    """Optionales Textfeld: leeren String zu None normalisieren."""
    if v is None:
        return None
    return v.strip() or None


def _opt_qty(v: Optional[Decimal]) -> Optional[Decimal]:
    """Optionale Mengenangabe (MOQ/Sicherheitsbestand): ≥ 0, max. 3 Nachkommastellen."""
    if v is None:
        return None
    try:
        d = Decimal(v)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Wert muss eine Zahl sein")
    if d < 0:
        raise ValueError("Wert darf nicht negativ sein")
    if d.as_tuple().exponent < -3:
        raise ValueError("Höchstens 3 Nachkommastellen erlaubt")
    return d


# Optionale Stammdatenfelder (dynamische Feldliste): Validatoren je Feld.
_OPTIONAL_TEXT_FIELDS = ("material", "cad_url", "surface", "supplier_article_number")
_OPTIONAL_QTY_FIELDS = ("min_order_qty", "safety_stock")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ArticleCreate(BaseModel):
    """Anlage eines Artikels über den '+'-Button. Status startet immer als 'draft'.

    Pflicht ist einzig der **Name**. Einheit/Serialisierung tragen einen Default
    (Stk / Einzelteil), Grösse & Gewicht sind optional (physische Attribute, die z. B. ein
    Dokument-Artikel nicht braucht). Es gibt KEINE Typ-Unterscheidung physisch/nicht-physisch:
    ob ein Dokument entsteht, entscheidet allein der Prozessschritt «document»."""

    name: str
    unit: Optional[str] = None            # Default 'Stk' (siehe ``_defaults``)
    serialization: Optional[str] = None   # Default 'unit'
    size: Optional[str] = None            # optional
    weight_kg: Optional[Decimal] = None   # optional
    # Optionale Stammdaten (nur bei Bedarf gepflegt)
    material: Optional[str] = None
    cad_url: Optional[str] = None
    surface: Optional[str] = None
    supplier_article_number: Optional[str] = None
    min_order_qty: Optional[Decimal] = None
    safety_stock: Optional[Decimal] = None
    # Beschaffungsquelle (Spezifikation): Modus + Lieferant/Webshop-Link (alle optional –
    # kann später ergänzt werden; der purchase-Schritt erbt sie als Default).
    procurement_mode: Optional[str] = None   # Default 'supplier'
    default_supplier_id: Optional[int] = None
    default_webshop_url: Optional[str] = None

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def _opt_text_clean(cls, v: Optional[str]) -> Optional[str]:
        return _opt_text(v)

    @field_validator(*_OPTIONAL_QTY_FIELDS)
    @classmethod
    def _opt_qty_clean(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _opt_qty(v)

    @field_validator("procurement_mode")
    @classmethod
    def _proc_mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_PROCUREMENT_MODES:
            raise ValueError("Beschaffungsmodus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("default_webshop_url")
    @classmethod
    def _proc_url_ok(cls, v: Optional[str]) -> Optional[str]:
        return _clean_webshop_url(v)

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        return clean_article_name(v, required=True)

    @field_validator("unit")
    @classmethod
    def _unit_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_UNITS:
            raise ValueError(f"Einheit muss eine von {', '.join(ALLOWED_UNITS)} sein")
        return v

    @field_validator("serialization")
    @classmethod
    def _serialization_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_SERIALIZATION:
            raise ValueError("Seriennummererfassung muss 'unit' (Einzelteil) oder 'batch' sein")
        return v

    @field_validator("size")
    @classmethod
    def _size_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_size(v)

    @field_validator("weight_kg")
    @classmethod
    def _weight_valid(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        return validate_weight(v)

    @model_validator(mode="after")
    def _defaults(self) -> "ArticleCreate":
        # Einheit/Serialisierung bekommen einen sinnvollen Default; Grösse/Gewicht bleiben
        # optional (leer, wenn nicht angegeben – z. B. bei einem Dokument-Artikel).
        self.unit = self.unit or "Stk"
        self.serialization = self.serialization or "unit"
        self.procurement_mode = self.procurement_mode or "supplier"
        return self


class ArticleUpdate(BaseModel):
    """Teil-Update aus dem Detailfenster. Alle Felder optional."""

    status: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    serialization: Optional[str] = None
    size: Optional[str] = None
    weight_kg: Optional[Decimal] = None
    material: Optional[str] = None
    cad_url: Optional[str] = None
    surface: Optional[str] = None
    supplier_article_number: Optional[str] = None
    min_order_qty: Optional[Decimal] = None
    safety_stock: Optional[Decimal] = None
    # Beschaffungsquelle (Spezifikation; im Entwurf editierbar, bei Freigabe eingefroren)
    procurement_mode: Optional[str] = None
    default_supplier_id: Optional[int] = None
    default_webshop_url: Optional[str] = None
    is_active: Optional[bool] = None
    # Optimistic Locking: Stand, den der Client zuletzt gesehen hat (optional).
    expected_updated_at: Optional[datetime] = None

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def _opt_text_clean(cls, v: Optional[str]) -> Optional[str]:
        return _opt_text(v)

    @field_validator(*_OPTIONAL_QTY_FIELDS)
    @classmethod
    def _opt_qty_clean(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _opt_qty(v)

    @field_validator("procurement_mode")
    @classmethod
    def _proc_mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_PROCUREMENT_MODES:
            raise ValueError("Beschaffungsmodus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("default_webshop_url")
    @classmethod
    def _proc_url_ok(cls, v: Optional[str]) -> Optional[str]:
        return _clean_webshop_url(v)

    @field_validator("status")
    @classmethod
    def _status_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_STATUS:
            raise ValueError(f"Status muss eine von {', '.join(ALLOWED_STATUS)} sein")
        return v

    @field_validator("name")
    @classmethod
    def _name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        return clean_article_name(v, required=False)

    @field_validator("unit")
    @classmethod
    def _unit_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_UNITS:
            raise ValueError(f"Einheit muss eine von {', '.join(ALLOWED_UNITS)} sein")
        return v

    @field_validator("serialization")
    @classmethod
    def _serialization_allowed(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_SERIALIZATION:
            raise ValueError("Seriennummererfassung muss 'unit' (Einzelteil) oder 'batch' sein")
        return v

    @field_validator("size")
    @classmethod
    def _size_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_size(v)

    @field_validator("weight_kg")
    @classmethod
    def _weight_valid(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is None:
            return v
        return validate_weight(v)


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    status: str
    name: str
    unit: str
    serialization: str
    size: Optional[str] = None
    weight_kg: Optional[Decimal] = None
    # Optionale Stammdaten (dynamische Feldliste)
    material: Optional[str] = None
    cad_url: Optional[str] = None
    surface: Optional[str] = None
    supplier_article_number: Optional[str] = None
    min_order_qty: Optional[Decimal] = None
    safety_stock: Optional[Decimal] = None
    # Beschaffungsquelle (Spezifikation) + denormalisierter Lieferantenname (Router)
    procurement_mode: str = "supplier"
    default_supplier_id: Optional[int] = None
    default_supplier_name: Optional[str] = None
    default_supplier_object_id: Optional[int] = None
    default_webshop_url: Optional[str] = None
    landed_unit_cost: Optional[Decimal] = None  # read-only, aus letzter Freigabe
    # Verkauf/Shop (bewusst lebende Ebene – auch nach der Freigabe editierbar)
    sales_published: bool = False
    sales_visibility: str = "public"
    sales_fulfillment: str = "make"
    # Aufsummiertes Gewicht aus den verbauten Ressourcen (read-only, rekursiv über
    # die Stückliste). Nur gesetzt, wenn der Artikel consume-Ressourcen hat.
    computed_weight_kg: Optional[Decimal] = None
    # Ersetzen (Nachvollziehbarkeit): Nachfolger bzw. Vorgänger (Objektnummern).
    replaced_by_id: Optional[int] = None
    replaces_id: Optional[int] = None  # vom Router gesetzt (Vorgänger)
    # Stückpreis-Spanne netto (Bestellsumme ÷ Menge) über akzeptierte Bestellungen
    unit_cost_low: Optional[Decimal] = None
    unit_cost_high: Optional[Decimal] = None
    # Durchlaufzeit-Spanne in Tagen (Freigabe → Abschluss) über erledigte Aufträge
    lead_time_days_low: Optional[float] = None
    lead_time_days_high: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ArticleNameSuggestion(BaseModel):
    """Ein Namensvorschlag beim Anlegen eines Artikels (freie Namensgebung, aber das
    System schlägt bereits verwendete/ähnliche Namen vor, um Dubletten zu vermeiden)."""
    name: str
    count: int = 0                       # wie viele aktive Artikel diesen Namen bereits tragen
    score: Optional[float] = None        # Ähnlichkeit zur Eingabe (nur bei Suche gesetzt)
