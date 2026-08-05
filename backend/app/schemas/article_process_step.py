from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..domain.event_types import STEP_TYPES as ALLOWED_STEP_TYPES
from ..services.article_fields import normalize_shared_fields
from .movement import LOCATION_TYPES

# Schritttypen kommen aus der deklarativen Registry (``domain.event_types``) – EINE
# Quelle der Wahrheit. EIN «resource»-Schritt («Ressource») fasst Verbrauch &
# Betriebsmittel zusammen; pro Zeile entscheidet ``mode`` (consume = verbraucht/FIFO/
# Lagerabgang | tool = Betriebsmittel, nur genutzt) – Default consume.
ALLOWED_MODES = ("supplier", "webshop")
# Erfassungsfeld-Typen der Datenerfassung – Bild & Unterschrift sind EIGENE Feldtypen
# (gleichrangig neben Soll-Ist/Gut-Schlecht/Text), keine übergeordneten Schritt-Optionen mehr.
ALLOWED_CAPTURE_TYPES = ("measure", "bool", "text", "photo", "signature")
ALLOWED_RESOURCE_MODES = ("consume", "tool")
ALLOWED_SIGN_ACTIONS = ("confirm", "sign")
ALLOWED_AUDIENCE = ("all", "roles", "persons")
ALLOWED_VISIBILITY = ("public", "internal", "confidential")
ALLOWED_AUDIENCE_ROLES = ("customer", "supplier", "employee", "admin")


class DocSigner(BaseModel):
    """Eine deklarierte **Freigabe-Partei** eines Dokument-Schritts (geordnet).

    ``signer_object_id`` = Objektnummer der Person; ``action`` = ``confirm`` (bestätigen,
    ohne Bild) | ``sign`` (unterschreiben, mit Unterschrift-Bild)."""

    signer_object_id: int
    action: str = "sign"

    @field_validator("action")
    @classmethod
    def _action_ok(cls, v: str) -> str:
        if v not in ALLOWED_SIGN_ACTIONS:
            raise ValueError("action muss 'confirm' (bestätigen) oder 'sign' (unterschreiben) sein")
        return v


def normalize_doc_signers(rows: Optional[list]) -> Optional[list[dict]]:
    """Freigabe-Parteien säubern: eindeutige Objektnummern, Reihenfolge erhalten."""
    if not rows:
        return None
    out: list[dict] = []
    seen: set[int] = set()
    for raw in rows:
        s = raw if isinstance(raw, DocSigner) else DocSigner(**raw)
        if s.signer_object_id in seen:
            continue
        seen.add(s.signer_object_id)
        out.append(s.model_dump())
    return out or None


def _check_target_location_type(v: Optional[str]) -> Optional[str]:
    """Vorgabe-Zieltyp der Bewegung (leer = Lagerist entscheidet frei)."""
    if v is None or v == "":
        return None
    if v not in LOCATION_TYPES:
        raise ValueError(f"Zieltyp muss eine von {', '.join(LOCATION_TYPES)} sein")
    return v


class CaptureField(BaseModel):
    """Ein Erfassungsfeld der Datenerfassung (Prozessschritt «inspection»)."""

    key: str = ""
    label: str
    # measure (Soll-Ist) | bool (Gut/Schlecht) | text | photo (Bild) | signature (Unterschrift)
    type: str = "measure"
    target: Optional[float] = None   # Sollwert (measure)
    tolerance: Optional[float] = None  # ± Toleranz (measure)
    unit: Optional[str] = None

    @field_validator("type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ALLOWED_CAPTURE_TYPES:
            raise ValueError(f"Feldtyp muss eine von {', '.join(ALLOWED_CAPTURE_TYPES)} sein")
        return v

    @field_validator("label")
    @classmethod
    def _label_ok(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("Bezeichnung des Erfassungsfelds fehlt")
        return v


class ResourceLine(BaseModel):
    """Eine Zeile eines Ressourcen-Schritts (Artikel + Menge pro Stück Produkt).

    ``mode`` bestimmt das Verhalten der Zeile: ``consume`` (verbraucht → Lagerabgang,
    FIFO) oder ``tool`` (Betriebsmittel → nur genutzt). Default ``consume``."""

    article_id: int
    quantity: float = 1             # Menge pro Stück Produkt (BOM) – Bruchmenge möglich (0.5 kg)
    mode: str = "consume"

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ALLOWED_RESOURCE_MODES:
            raise ValueError("Modus muss 'consume' (Verbrauch) oder 'tool' (Betriebsmittel) sein")
        return v

    @field_validator("quantity")
    @classmethod
    def _qty_ok(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Menge muss grösser als 0 sein")
        return v


class ResourceLineView(ResourceLine):
    """Ressourcen-Zeile mit denormalisiertem Artikel (für Responses/Embeds)."""

    article_name: Optional[str] = None
    article_object_id: Optional[int] = None
    unit: Optional[str] = None
    serialization: Optional[str] = None


def normalize_capture_fields(fields: Optional[list]) -> list[dict]:
    """Erfassungsfelder validieren, Keys vergeben/eindeutig machen."""
    out: list[dict] = []
    seen: set[str] = set()
    for i, raw in enumerate(fields or []):
        cf = raw if isinstance(raw, CaptureField) else CaptureField(**raw)
        key = (cf.key or "").strip() or f"feld_{i + 1}"
        while key in seen:
            key = f"{key}_{i + 1}"
        seen.add(key)
        d = cf.model_dump()
        d["key"] = key
        if cf.type != "measure":
            d["target"] = None
            d["tolerance"] = None
        out.append(d)
    return out


def _clean_url(v: Optional[str]) -> Optional[str]:
    """Webshop-Link säubern und auf ein gültiges http(s)-URL prüfen."""
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    parsed = urlparse(v)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        raise ValueError("Bitte einen gültigen Link angeben (z. B. https://shop.example.com/…)")
    return v


def _check_percent(v: Optional[int]) -> Optional[int]:
    if v is None:
        return v
    if not (1 <= v <= 100):
        raise ValueError("Prüfumfang muss zwischen 1 und 100 % liegen")
    return v


class ArticleProcessStepCreate(BaseModel):
    """Anlage eines Prozessschritts im Reiter «Prozess» des Artikels."""

    step_type: str = "purchase"
    position: Optional[int] = None
    mode: str = "supplier"
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    sample_percent: Optional[int] = None
    capture_fields: Optional[list[CaptureField]] = None
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    resource_lines: Optional[list[ResourceLine]] = None
    # «document»-Deklaration (Struktur der Freigabe/Anerkennung – gilt für alle Ausfertigungen)
    doc_signers: Optional[list[DocSigner]] = None
    sign_sequential: bool = False
    doc_audience: Optional[str] = None
    doc_audience_roles: Optional[list[str]] = None
    doc_audience_person_ids: Optional[list[int]] = None
    doc_visibility: str = "internal"

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> list[str]:
        return normalize_shared_fields(v)

    @field_validator("doc_audience")
    @classmethod
    def _audience_ok(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, "", "none"):
            return None
        if v not in ALLOWED_AUDIENCE:
            raise ValueError(f"Publikum muss eine von {', '.join(ALLOWED_AUDIENCE)} sein")
        return v

    @field_validator("doc_visibility")
    @classmethod
    def _visibility_ok(cls, v: str) -> str:
        if v not in ALLOWED_VISIBILITY:
            raise ValueError(f"Sichtbarkeit muss eine von {', '.join(ALLOWED_VISIBILITY)} sein")
        return v

    @field_validator("doc_audience_roles")
    @classmethod
    def _aud_roles_ok(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if not v:
            return None
        bad = [r for r in v if r not in ALLOWED_AUDIENCE_ROLES]
        if bad:
            raise ValueError(f"Unbekannte Rolle(n): {', '.join(bad)}")
        return list(dict.fromkeys(v))

    @field_validator("target_location_type")
    @classmethod
    def _target_type_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_target_location_type(v)


    @field_validator("step_type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in ALLOWED_STEP_TYPES:
            raise ValueError(f"Schritt-Typ muss eine von {', '.join(ALLOWED_STEP_TYPES)} sein")
        return v

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ALLOWED_MODES:
            raise ValueError("Modus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("webshop_url")
    @classmethod
    def _url_clean(cls, v: Optional[str]) -> Optional[str]:
        return _clean_url(v)

    @field_validator("sample_percent")
    @classmethod
    def _pct_ok(cls, v: Optional[int]) -> Optional[int]:
        return _check_percent(v)

    @model_validator(mode="after")
    def _consistent(self) -> "ArticleProcessStepCreate":
        # Bezugsquelle gehört zur **Artikel-Spezifikation** (``articles.procurement_*``); der
        # Beschaffungs-Schritt ERBT sie und braucht daher KEINE eigene Quelle. Optional kann er
        # sie pro Fall überschreiben (``supplier_id`` bzw. ``webshop_url``) – keine Pflicht mehr.
        if self.step_type == "inspection" and self.sample_percent is None:
            self.sample_percent = 100  # Default: ganze Menge prüfen
        # **Ein Modul entsteht leer und wird IM Fluss konfiguriert** (Testnotiz #635): eine
        # Datenerfassung ohne Feld und eine Ressource ohne Zeile sind darum beim Anlegen
        # erlaubt. Unvollständig bleiben dürfen sie trotzdem nicht – geprüft wird bei der
        # **Freigabe** (``processes.incomplete_steps``), also an dem Gate, ab dem der Prozess
        # wirklich läuft. Das ist keine Lockerung, sondern der richtige Zeitpunkt: vorher
        # zwang die Prüfung zu einem Anlage-Formular mit «Abbrechen»/«Hinzufügen».
        # Zielstandort – Bewegung: Ziel; Beschaffung: Lieferadresse/Wareneingang.
        # Ohne Zieltyp gibt es kein festes Zielobjekt.
        if self.target_location_type is None:
            self.target_location_id = None
        return self


class StepReorder(BaseModel):
    """Neue Reihenfolge der (frei sortierbaren) Nutzer-Schritte – Pflicht-Bewegungen
    werden serverseitig automatisch neu eingefügt/positioniert."""

    ordered_ids: list[int]


class ArticleProcessStepUpdate(BaseModel):
    """Teil-Update eines Prozessschritts.

    ``step_type`` ist **nur innerhalb des Moduls «Aussondern»** änderbar (scrap ↔ block):
    das ist EIN Modul mit zwei Wirkungen (#277), und die Wirkung ist eine Konfiguration,
    keine andere Sache. Der Router erzwingt das (``_update``)."""

    step_type: Optional[str] = None
    position: Optional[int] = None
    mode: Optional[str] = None
    supplier_id: Optional[int] = None
    webshop_url: Optional[str] = None
    shared_fields: Optional[list[str]] = None
    sample_percent: Optional[int] = None
    capture_fields: Optional[list[CaptureField]] = None
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    resource_lines: Optional[list[ResourceLine]] = None
    doc_signers: Optional[list[DocSigner]] = None
    sign_sequential: Optional[bool] = None
    doc_audience: Optional[str] = None
    doc_audience_roles: Optional[list[str]] = None
    doc_audience_person_ids: Optional[list[int]] = None
    doc_visibility: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("step_type")
    @classmethod
    def _type_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_STEP_TYPES:
            raise ValueError(f"Schritt-Typ muss eine von {', '.join(ALLOWED_STEP_TYPES)} sein")
        return v

    @field_validator("shared_fields")
    @classmethod
    def _shared_ok(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        return normalize_shared_fields(v)

    @field_validator("doc_audience")
    @classmethod
    def _audience_ok(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, "", "none"):
            return None
        if v not in ALLOWED_AUDIENCE:
            raise ValueError(f"Publikum muss eine von {', '.join(ALLOWED_AUDIENCE)} sein")
        return v

    @field_validator("doc_visibility")
    @classmethod
    def _visibility_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in ALLOWED_VISIBILITY:
            raise ValueError(f"Sichtbarkeit muss eine von {', '.join(ALLOWED_VISIBILITY)} sein")
        return v

    @field_validator("target_location_type")
    @classmethod
    def _target_type_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_target_location_type(v)


    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_MODES:
            raise ValueError("Modus muss 'supplier' (Lieferant) oder 'webshop' sein")
        return v

    @field_validator("webshop_url")
    @classmethod
    def _url_clean(cls, v: Optional[str]) -> Optional[str]:
        return _clean_url(v)

    @field_validator("sample_percent")
    @classmethod
    def _pct_ok(cls, v: Optional[int]) -> Optional[int]:
        return _check_percent(v)


class ArticleProcessStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_id: Optional[int] = None
    order_id: Optional[int] = None
    position: int
    step_type: str
    # Begleit-Bewegung: vom System hinter Beschaffung/Verkauf gesät. **Rolle, keine Sperre** –
    # der Schritt ist wie jeder andere löschbar/verschiebbar/editierbar (früher ``locked``).
    companion: bool = False
    mode: str
    supplier_id: Optional[int]
    supplier_name: Optional[str] = None       # vom Router denormalisiert
    # Objektnummer des Lieferanten – ``supplier_id`` ist der interne Schlüssel und darf
    # NIE als Objektnummer angezeigt werden. Damit ist die Quelle im Prozess klickbar.
    supplier_object_id: Optional[int] = None
    webshop_url: Optional[str]
    shared_fields: list[str] = []
    sample_percent: Optional[int] = None
    capture_fields: list[CaptureField] = []
    target_location_type: Optional[str] = None
    target_location_id: Optional[int] = None
    resource_lines: list[ResourceLineView] = []
    # «document»-Deklaration
    doc_signers: list[DocSigner] = []
    sign_sequential: bool = False
    doc_audience: Optional[str] = None
    doc_audience_roles: list[str] = []
    doc_audience_person_ids: list[int] = []
    doc_visibility: str = "internal"
    is_active: bool
    created_at: datetime
    updated_at: datetime


    @field_validator("doc_signers", mode="before")
    @classmethod
    def _doc_signers_default(cls, v: Optional[list]) -> list:
        return v or []

    @field_validator("doc_audience_roles", "doc_audience_person_ids", mode="before")
    @classmethod
    def _aud_list_default(cls, v: Optional[list]) -> list:
        return v or []

    @field_validator("shared_fields", mode="before")
    @classmethod
    def _shared_default(cls, v: Optional[list]) -> list[str]:
        return normalize_shared_fields(v)

    @field_validator("capture_fields", mode="before")
    @classmethod
    def _capture_default(cls, v: Optional[list]) -> list:
        return v or []

    @field_validator("resource_lines", mode="before")
    @classmethod
    def _resource_default(cls, v: Optional[list]) -> list:
        return v or []
