"""Schemas für das Prozessschrittmodul «Dokument».

``DocumentContent`` ist die bewusst schlanke Struktur eines „Word"-artigen Textdokuments
(Titel + Untertitel + nummerierte Abschnitte). Der Inhalt wird **während der
Auftragsausführung** verfasst und mit «Ausstellen» festgeschrieben.

Nummer & Datum kommen nicht vom Dokument selbst, sondern von der **Instanz**, die der
Auftrag erzeugt: ``object_number`` = Instanz-Objektnummer, ``document_date`` =
``instances.released_at``. Keine eigene Objektnummer, keine Versionsnummer.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class DocumentSection(BaseModel):
    """Ein Abschnitt: Überschrift (z. B. «§1 Geltungsbereich») + Fliesstext (mehrzeilig)."""
    heading: str = ""
    body: str = ""


class DocumentContent(BaseModel):
    """Inhalt eines Dokuments – Titel/Untertitel + geordnete Abschnitte."""
    title: str = ""
    subtitle: Optional[str] = None
    sections: list[DocumentSection] = []


class DocumentUpdate(BaseModel):
    """Verfassen/Ausstellen des Dokuments am Auftragsschritt (analog Datenerfassung).

    ``action='save'`` speichert den Zwischenstand (Schritt bleibt offen), ``action='issue'``
    stellt das Dokument aus (Schritt erledigt, Inhalt festgeschrieben)."""

    step_id: Optional[int] = None
    content: DocumentContent
    action: str = "save"

    @field_validator("action")
    @classmethod
    def _action_ok(cls, v: str) -> str:
        if v not in ("save", "issue"):
            raise ValueError("action muss 'save' oder 'issue' sein")
        return v


class DocumentEmbed(BaseModel):
    """Eingebetteter Stand des Dokument-Schritts (im Auftrag).

    ``object_number`` (Instanz-Objektnummer) und ``document_date`` (Instanz-Freigabedatum)
    werden serverseitig aus der vom Auftrag erzeugten Instanz abgeleitet."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    done: bool = False
    content: Optional[DocumentContent] = None
    object_number: Optional[int] = None       # = Instanz-Objektnummer (die Dokumentennummer)
    document_date: Optional[datetime] = None   # = instances.released_at
    created_by_name: Optional[str] = None
