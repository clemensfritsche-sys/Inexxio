from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


def _check_name(v: str) -> str:
    v = (v or "").strip()
    if not v:
        raise ValueError("Name des Prozesses fehlt")
    return v


class ProcessCreate(BaseModel):
    """Anlage eines Prozesses (eigenständiges Objekt mit Objektnummer).

    Der **Name** ist frei. Es gibt **keine** Wahl der Quelle/Richtung – das Verhalten
    (erhöhend/mindernd/neutral) ergibt sich aus den **Schritten** des Prozesses.
    ``is_standard`` (global geerbt) ist optional (Favoriten-Markierung), nur bei der
    Anlage bzw. im Entwurf setzbar."""

    name: str
    position: Optional[int] = None
    is_standard: bool = False

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: str) -> str:
        return _check_name(v)


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[int] = None
    status: Optional[str] = None
    is_standard: Optional[bool] = None   # nur im Entwurf änderbar (Router erzwingt)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _name_ok(cls, v: Optional[str]) -> Optional[str]:
        return _check_name(v) if v is not None else v

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("draft", "released", "inactive"):
            raise ValueError("Status muss draft, released oder inactive sein")
        return v


class ProcessLinkCreate(BaseModel):
    """Einen bestehenden Prozess der Prozessstückliste eines Artikels hinzufügen."""

    process_id: int
    position: Optional[int] = None


class ProcessLinkReorder(BaseModel):
    """Neue Reihenfolge der Prozessstückliste (Prozess-IDs in Zielreihenfolge)."""

    ordered_process_ids: list[int]


class ProcessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    article_id: Optional[int] = None  # Herkunft (nicht Zugehörigkeit)
    name: str
    source: str
    is_standard: bool
    position: int
    status: str
    is_active: bool
    replaced_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    # denormalisiert (Router)
    step_count: int = 0
    # Deklarierte Lager-Richtung (Aggregat der Schritt-Polaritäten, NICHT gewählt):
    # increase | decrease | mixed | neutral. ``mixed`` = Zu- UND Abgang im Prozess.
    stock_effect: str = "neutral"
    # Vorgänger (Ersetzen-Kette) + Anzahl Artikel, die diesen Prozess führen.
    replaces_id: Optional[int] = None
    linked_article_count: int = 0
