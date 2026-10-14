from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Status einer Notiz – bewusst nur drei (Ampel): offen · erledigt · verworfen.
FEEDBACK_STATUSES = ("open", "done", "dismissed")

BODY_MAX = 2000
ROUTE_MAX = 500


class FeedbackAnchor(BaseModel):
    """WO die Notiz hängt. ``label`` (sichtbarer Text) ist der beste greppbare Anker."""

    label: str = Field(default="", max_length=200)
    tag: str = Field(default="", max_length=40)
    selector: str = Field(default="", max_length=500)
    html: str = Field(default="", max_length=800)
    # Umgebender Abschnitt (Prozessschritt-Panel, Sektionstitel) – bei den dynamischen
    # Listen des Prozess-Editors trägt er mehr als die Positions-Kette des Selektors.
    section: str = Field(default="", max_length=80)
    rx: float = 0.5   # relative Position im Element (0–1), damit der Pin wieder passt
    ry: float = 0.5


class FeedbackContext(BaseModel):
    """WOMIT es passiert ist – die Umgebung, die man von Hand nie sauber notiert."""

    viewport: str = Field(default="", max_length=40)
    ua: str = Field(default="", max_length=300)
    role: str = Field(default="", max_length=20)
    version: str = Field(default="", max_length=60)      # Build-Commit des Frontends
    view: str = Field(default="", max_length=80)         # offener Datensatz + Reiter («Artikel · Prozess»)
    errors: list[str] = Field(default_factory=list)      # letzte Laufzeitfehler (Ringpuffer)

    @field_validator("errors")
    @classmethod
    def _cap_errors(cls, v: list[str]) -> list[str]:
        """Ringpuffer hart begrenzen – eine Notiz ist kein Log-Sammler."""
        return [str(e)[:300] for e in v[-5:]]


class FeedbackCreate(BaseModel):
    body: str = Field(min_length=1, max_length=BODY_MAX)
    route: str = Field(default="", max_length=ROUTE_MAX)
    target_object_id: Optional[int] = None
    anchor: Optional[FeedbackAnchor] = None
    context: Optional[FeedbackContext] = None


class FeedbackUpdate(BaseModel):
    """Rückkopplung: erledigt/verworfen setzen (oder wieder öffnen) + Begründung."""

    status: Optional[str] = None
    resolution: Optional[str] = Field(default=None, max_length=BODY_MAX)

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in FEEDBACK_STATUSES:
            raise ValueError(f"status must be one of {FEEDBACK_STATUSES}")
        return v


class FeedbackNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    body: str
    route: str
    target_object_id: Optional[int] = None
    anchor: Optional[dict] = None
    context: Optional[dict] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    created_by: Optional[int] = None
    author_name: str = ""     # abgeleitet (wer hat gemeldet) – nicht am Modell gespeichert
    mine: bool = False        # darf ich sie bearbeiten/schliessen?
