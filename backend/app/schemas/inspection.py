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

    # Unterschrift und Foto sind reine **Erfassungsfeld-Typen** (``fields`` mit
    # ``type='signature'``/``'photo'``); ihre Werte stehen in den ``samples``. Die frühere
    # Parallel-Achse (require_*/signature_url/…) ist entfernt (Migration 081).

    @field_validator("samples", mode="before")
    @classmethod
    def _samples_default(cls, v: Optional[list]) -> list:
        return v or []
