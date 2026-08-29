import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import (BaseModel, ConfigDict, Field, field_validator,
                      model_validator)

from ..domain import statuses as st
from .process import ModuleFacts, ModuleInput

# ─── Erlaubte Werte ──────────────────────────────────────────────────────────

ALLOWED_UNITS = ("Stk", "mm", "m2", "m3", "kg", "l")
ALLOWED_SERIALIZATION = ("unit", "batch")
#: Aus der EINEN Statusliste (``domain/statuses.ARTICLE_STATUSES``) – hier nicht noch
#: einmal aufgezählt: eine zweite Liste liefe beim ersten neuen Wert auseinander.
ALLOWED_STATUS = st.ARTICLE_STATUSES

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
    """Der Artikel-Entwurf, so wie ihn die Oberfläche schickt – Spezifikation **und**
    Erzeugungsprozess in einem Aufruf.

    Das ist keine Bequemlichkeit, sondern die Folge aus der Regel: der Artikel entsteht
    erst mit seiner **Freigabe**, und die verlangt beides. Zwei Aufrufe hiessen zwei
    Transaktionen und damit die Möglichkeit eines halben Artikels – genau die, die es
    vorher gab (Spezifikation gespeichert, Prozess leer).

    Pflicht sind **Name, Abmessungen, Gewicht** und **mindestens ein Prozessschrittmodul**.
    Einheit/Serialisierung tragen einen Default (Stk / Einzelteil). Geprüft wird in
    ``services/articles.missing_for_release`` – der einen Stelle, die auch ``/validate``
    beantwortet."""

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
    is_hazmat: Optional[bool] = None            # Gefahrgut (reist mit dem Beschaffungs-Beleg)
    #: Der Erzeugungsprozess. **Pflicht** – ein Artikel ohne ihn kann nichts erzeugen.
    steps: list[ModuleInput] = Field(default_factory=list)
    #: **Welchen Artikel löst dieser hier ab?** (Objektnummer, optional.)
    #:
    #: Die Angabe steht am **Nachfolger**, weil sie genau einen Moment hat: die Anlage.
    #: Ein Feld am Vorgänger («wer löst mich ab?») wäre jederzeit änderbar und damit eine
    #: zweite Wahrheit über dieselbe Kette. Wirkung: ``predecessor.replaced_by_id`` zeigt
    #: hierher, **und** der Vorgänger geht ausser Betrieb – ein Vorgang, ein Aufruf.
    replaces_object_id: Optional[int] = None

    @field_validator(*_OPTIONAL_TEXT_FIELDS)
    @classmethod
    def _opt_text_clean(cls, v: Optional[str]) -> Optional[str]:
        return _opt_text(v)

    @field_validator(*_OPTIONAL_QTY_FIELDS)
    @classmethod
    def _opt_qty_clean(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        return _opt_qty(v)

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
    is_hazmat: Optional[bool] = None            # Gefahrgut (reist mit dem Beschaffungs-Beleg)
    # Beschaffungsquelle (Spezifikation; im Entwurf editierbar, bei Freigabe eingefroren)
    # **``is_active`` steht hier bewusst NICHT.** Ein Artikel wird über genau EINE Achse
    # ausser Betrieb genommen: seinen fachlichen ``status`` (Freigegeben ↔ Inaktiv).
    # ``is_active`` ist der Soft-Delete des Datensatzes und gehört keinem Formular –
    # solange er von aussen setzbar war, gab es zwei Wege, dasselbe zu sagen, und die
    # Prozesslogik las den falschen (``articles.may_create``).
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


class ArticleLink(BaseModel):
    """Ein Artikel, wie ihn eine andere Antwort **nennt**: Nummer, Name, Zustand.

    Der Zustand reist mit, weil er die Aussage trägt: «Schraube M6 (ausser Betrieb)» ist
    eine Warnung, «Schraube M6» ist eine Angabe. Ihn beim Empfänger nachzuladen hiesse,
    je Zeile eine Abfrage zu fahren.
    """

    object_id: int
    name: str
    status: str


class RetiredInput(BaseModel):
    """Ein **ausser Betrieb genommener** Artikel in der Stückliste dieses Artikels."""

    article: ArticleLink
    #: Der Weg dorthin – die Artikel dazwischen, von mir aus gesehen. Leer heisst:
    #: er steht **direkt** in meiner Stückliste.
    via: list[ArticleLink] = Field(default_factory=list)
    #: Der Nachfolger, wenn es einen gibt – die **Lösung** steht dort, wo das Problem
    #: gemeldet wird.
    replaced_by: Optional[ArticleLink] = None


class ArticleBom(BaseModel):
    """Die **geplante** Stückliste in beide Richtungen (``services/bom.py``).

    Nur am Detail gefüllt, nie im Feed: sie kostet zwei Abfragen je Artikel, und im Feed
    wären das zweihundert. ``None`` an der Antwort heisst darum «nicht geladen», nicht
    «nichts gefunden» – die beiden zu verwechseln hiesse, im Feed jedem Artikel eine
    leere Stückliste zu attestieren.
    """

    #: Wer nennt mich in seiner Stückliste? Die Antwort auf «was mache ich kaputt, wenn
    #: ich diesen Artikel ausser Betrieb nehme».
    used_in: list[ArticleLink] = Field(default_factory=list)
    #: Was in meiner Stückliste steckt und ausser Betrieb ist – direkt oder über Stufen.
    retired_inputs: list[RetiredInput] = Field(default_factory=list)


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
    is_hazmat: bool = False                     # Gefahrgut (reist mit dem Beschaffungs-Beleg)
    landed_unit_cost: Optional[Decimal] = None  # read-only, aus der letzten Bestellung
    # Die Erfassungsmaske der Datenerfassung: was an einer Einzelinstanz dieses
    # ── Ersetzen: die Kette in beide Richtungen ────────────────────────────────
    #: Die rohe Kante, wie sie in der Zeile steht (``articles.replaced_by_id``).
    replaced_by_id: Optional[int] = None
    #: Aufgelöst – Nummer **und** Name **und** Zustand. Vom Router gefüllt; die rohe
    #: Nummer allein zwänge jede Anzeige zu einer eigenen Abfrage, nur um ein Wort
    #: danebenzuschreiben.
    replaced_by: Optional[ArticleLink] = None
    #: Die Gegenrichtung: wen löst dieser Artikel ab? **Abgefragt, nicht gespiegelt** –
    #: eine zweite Spalte wäre die zweite Stelle, an der die Kette auseinanderläuft.
    replaces: Optional[ArticleLink] = None
    #: Die geplante Stückliste – **nur am Detail** (``None`` = nicht geladen).
    bom: Optional[ArticleBom] = None
    # Einstandspreis und Durchlaufzeit sind entfallen: beide wurden aus abgeschlossenen
    # Aufträgen abgeleitet, und Aufträge gibt es nicht mehr. Eine Zahl ohne Grundlage
    # wäre schlechter als keine.
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ArticleValidation(BaseModel):
    """Antwort auf «wäre dieser Entwurf freigebbar?» – ohne etwas anzulegen."""

    saveable: bool
    missing: list[str] = Field(
        default_factory=list,
        description="Was noch fehlt – leer heisst freigebbar.",
    )


class ArticleNameSuggestion(BaseModel):
    """Ein Namensvorschlag beim Anlegen eines Artikels (freie Namensgebung, aber das
    System schlägt bereits verwendete/ähnliche Namen vor, um Dubletten zu vermeiden)."""
    name: str
    count: int = 0                       # wie viele aktive Artikel diesen Namen bereits tragen
    score: Optional[float] = None        # Ähnlichkeit zur Eingabe (nur bei Suche gesetzt)


# ---------------------------------------------------------------------------
# Erzeugungsprozess (Vorlage am Artikel)
# ---------------------------------------------------------------------------

class ArticleProcessStepResponse(ModuleFacts):
    """Ein Modul der Vorlage. Dieselbe Form wie im Auftrag – es ist derselbe Prozess,
    nur bevor er läuft.

    Beschriftung, Farbfamilie und «Ausgang?» kommen aus ``ModuleFacts`` – derselben
    Ableitung wie im Auftrag. Zwei Wege dorthin wären zwei Stände.
    """

    #: **Die Identität des Moduls** (#687). Der Ereignis-Log zeigt auf sie und auf
    #: nichts sonst – nicht auf einen Namen, nicht auf die Position.
    id: int
    position: int
    status_before: str
    status_after: str
    config: Optional[dict] = None


class ArticleProcess(BaseModel):
    """Der Erzeugungsprozess eines Artikels samt Versionsstempel.

    ``version`` ist der Stand, der bei einer Freigabe auf die Kopie geschrieben wird –
    er macht an einem laufenden Auftrag ablesbar, welche Fassung er fährt."""

    version: int
    steps: list[ArticleProcessStepResponse] = Field(default_factory=list)
