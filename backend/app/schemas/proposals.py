"""Phase 3 · KI – Erfassen, Vorschläge, das Angeheftete (``docs/konzept/phase3-bauplan.md``).

Die Formen hier SIND der Vertrag mit der Oberfläche (Bauplan «API»): ``Intake``, ``Part``,
``Proposal``, ``Pinned``. Alles, was sie tragen, steht im Log (Ereignisse ``intake``,
``proposal``, ``proposal.decided``, ``pin``, ``pin.solved``) – keine eigene Tabelle.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class IntakePart(BaseModel):
    """**Ein Teil einer Erfassung** – wohin er gehört (Datensatz), was dort steht, Betreff."""

    object_id: int
    #: «Benutzer · Hans Muster» (``records.Record.label``).
    label: str = ""
    text: str
    subject: str = ""


class PartIn(BaseModel):
    """Ein Teil, wie der Mensch ihn ablegt («Stimmt so»)."""

    object_id: int
    #: So lang wie eine abgeschriebene Aufnahme (``intake.MAX_SPOKEN``); eine Notiz trägt
    #: höchstens ``intake.MAX_TEXT`` – längere Teile werden zu mehreren Notizen (``intake.pieces``).
    text: str = Field(max_length=200_000)
    subject: Optional[str] = Field(None, max_length=255)


class IntakeIn(BaseModel):
    """**Etwas festhalten** – der Text und der Datensatz, der dabei offen war (Hinweis)."""

    text: str = Field(max_length=20000)
    hint_object_id: Optional[int] = None


class FileIn(BaseModel):
    """«Stimmt so» – die Teile, wie sie abgelegt werden (je Teil eine Notiz)."""

    parts: list[PartIn]


class NoteRef(BaseModel):
    """Eine Notiz, die beim Ablegen entstand."""

    object_id: int
    message_id: int


class DraftOut(BaseModel):
    """Der Entwurf eines ``create``-Vorschlags – vorausgefüllt in «Entwurf öffnen»."""

    type: Literal["user", "organization"]
    values: dict[str, str] = {}


class ProposalSource(BaseModel):
    """Woher ein Vorschlag kommt («Erfassung von Hans-Peter», «Mail von Vreni Kunz: …»), kurz –
    nie die Worte einer Erfassung."""

    text: str = ""
    object_id: Optional[int] = None
    #: Die Erfassung (Log-Id des ``intake``), aus der er kam – bei ``file`` immer gesetzt.
    intake: Optional[int] = None
    at: Optional[datetime] = None


class AiProposal(BaseModel):
    """►►► **Ein Vorschlag** – ``id`` ist die Nummer seines Ereignisses im Log. ◄◄◄"""

    id: int
    at: datetime
    object_id: int
    object_label: str = ""
    kind: Literal["change", "create", "file"]
    #: Nur ``change``: der Spaltenname (``proposals.FIELDS``) – derselbe wie ``name`` am Feld.
    field: Optional[str] = None
    #: Das Wort: «Telefon», «Neue Person», «Ablegen».
    label: str = ""
    #: Nur ``change``: der vorgeschlagene Wert.
    value: Optional[str] = None
    #: Nur ``change``: der heutige Wert des Feldes.
    current: Optional[str] = None
    draft: Optional[DraftOut] = None
    parts: Optional[list[IntakePart]] = None
    source: ProposalSource


class IntakeOut(BaseModel):
    """►►► **Eine Erfassung** – ``id`` ist die Nummer ihres Ereignisses ``intake``. ◄◄◄"""

    id: int
    at: datetime
    text: str
    hint_object_id: Optional[int] = None
    #: Wohin sie gehört – der Vorschlag der KI, sonst ein Teil (der ganze Text am Hinweis
    #: bzw. an der Person).
    parts: list[IntakePart] = []
    #: Was daraus folgt (offene ``change``/``create``).
    proposals: list[AiProposal] = []
    filed: bool = False
    notes: list[NoteRef] = []
    #: Warum die KI (noch) nicht abgelegt hat – ein Satz, oder leer.
    problem: Optional[str] = None


class PinHint(BaseModel):
    key: str
    text: str
    #: Der Eintrag des Verlaufs, auf den der Hinweis zeigt (``HistoryEntry.key``) – oder leer.
    entry_key: Optional[str] = None


class PinnedOut(BaseModel):
    """►►► **Das Angeheftete eines Datensatzes** – offene Vorschläge immer zuerst, dann die
    Hinweise der KI (vom letzten «neu ansehen»), ohne die gelösten. ◄◄◄"""

    proposals: list[AiProposal] = []
    hints: list[PinHint] = []
    refreshed_at: Optional[datetime] = None
    problem: Optional[str] = None


class SolveIn(BaseModel):
    key: str
