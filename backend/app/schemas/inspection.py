from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .article_process_step import CaptureField


class InspectionSample(BaseModel):
    """Eine zu prüfende Stichprobe: konkrete Instanz (+ Probe-Nr. bei Charge)."""

    instance_id: int            # object_id der Instanz
    slot: int = 1               # 1 bei Einzelteil; 1..N bei Charge (mehrere Proben)
    values: dict = {}           # erfasste Werte der Maske {field_key: value}
    photos: list[str] = []      # Foto-Belege (Attachment-URLs)

    @field_validator("values", mode="before")
    @classmethod
    def _values_default(cls, v: Optional[dict]) -> dict:
        return v or {}

    @field_validator("photos", mode="before")
    @classmethod
    def _photos_default(cls, v: Optional[list]) -> list:
        return v or []


class InspectionUpdate(BaseModel):
    """Erfassung der Datenerfassung – je aufgeführter Stichprobe ein Wertesatz.

    Das Ergebnis (passed/failed) leitet sich aus allen Stichproben ab: bestanden,
    wenn jede Probe alle bewertbaren Felder erfüllt.
    """

    samples: list[InspectionSample] = []
    note: Optional[str] = None
    step_id: Optional[int] = None   # konkrete Schritt-Definition (Mehr-Operationen-Routing)
    signature_url: Optional[str] = None   # digitale Unterschrift (Bild-URL), falls Freigabe verlangt
    photo_url: Optional[str] = None       # Schritt-Foto («Bilderfassung»), falls verlangt


class InspectionEmbed(BaseModel):
    """Eingebetteter Stand der Datenerfassung (im Auftrag)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    result: str
    checked_count: Optional[int]
    note: Optional[str]

    # Vom Router berechnet/denormalisiert
    sample_percent: Optional[int] = None
    required_count: Optional[int] = None
    escalated: bool = False             # auf 100 % hochgestuft (Stichprobe ungenügend)
    inspector_name: Optional[str] = None
    fields: list[CaptureField] = []     # Maske (aus der Prozessdefinition)
    samples: list[InspectionSample] = []  # konkrete Stichproben (Instanz + erfasste Werte)

    # Freigabe/Unterschrift + Bilderfassung (Konfiguration aus der Definition + erfasste Werte).
    require_signature: bool = False
    signer_ids: list[int] = []          # zugelassene Unterzeichner (Objektnummern); leer = jede/r
    signature_url: Optional[str] = None
    signed_by_name: Optional[str] = None
    signed_at: Optional[datetime] = None
    require_photo: bool = False
    photo_instruction: Optional[str] = None
    photo_url: Optional[str] = None

    @field_validator("samples", mode="before")
    @classmethod
    def _samples_default(cls, v: Optional[list]) -> list:
        return v or []
