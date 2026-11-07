"""Phase 4 · Sprache – die Aufnahme (``docs/konzept/phase4-bauplan.md``, «API»).

Die Form hier IST der Vertrag mit der Oberfläche: ``Recording``. Alles, was sie trägt, steht im
Log (``recording.start`` · ``.stop`` · ``.segment`` · ``.done`` · ``.failed``); die Stücke
verzeichnet ``recording_chunks``, bis sie abgeschrieben sind.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .proposals import IntakeOut


class RecordingIn(BaseModel):
    """**Eine Aufnahme beginnen** – der Datensatz, der offen war (Hinweis), und die Sorte, die
    der Browser aufnimmt (``audio/webm;codecs=opus``, Safari ``audio/mp4``)."""

    hint_object_id: Optional[int] = None
    mime: str = Field(max_length=100)


class StopIn(BaseModel):
    """**Stopp** – wie viele Abschnitte (je 5 Minuten, ab 0 gezählt) es gab."""

    segments: int = Field(ge=0)


RecordingState = Literal["recording", "transcribing", "filing", "done", "failed"]


class Recording(BaseModel):
    """►►► **Eine Aufnahme** – ``id`` ist die Nummer ihres ``recording.start`` im Log. ◄◄◄

    ``state``: ``recording`` (kein Stopp, nicht abgebrochen) · ``transcribing`` (gestoppt,
    Abschnitte fehlen) · ``filing`` (Text da, die Erfassung entsteht) · ``done`` (die Erfassung
    gibt es, ``intake`` gesetzt) · ``failed`` (``problem``)."""

    id: int
    at: datetime
    hint_object_id: Optional[int] = None
    mime: str
    state: RecordingState
    #: Die bekannten Abschnitte (aus Stopp und Stücken).
    segments: int = 0
    #: Davon abgeschrieben (oder mit Vermerk übersprungen).
    transcribed: int = 0
    #: Ungefähre Länge – je Stück 30 s.
    seconds: int = 0
    #: Die Erfassung, sobald es sie gibt – die Oberfläche öffnet «Abgelegt».
    intake: Optional[IntakeOut] = None
    problem: Optional[str] = None
