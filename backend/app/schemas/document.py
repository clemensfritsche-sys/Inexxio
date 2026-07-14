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


class DocumentContent(BaseModel):
    """Inhalt eines Dokuments – Titel/Untertitel + **Markdown-Fliesstext** (``body``).

    Der Body ist Markdown (GitHub-Flavored): Überschriften, **fett**/*kursiv*, Aufzählungen,
    nummerierte Listen, Tabellen, Links, Bilder, Zitate, Code. So kann die KI reichhaltige
    Dokumente erzeugen und der Mensch sie mit einer Werkzeugleiste bearbeiten. Web-Render via
    react-markdown, PDF via markdown→HTML→WeasyPrint (einheitliches Inexxio-Design)."""
    title: str = ""
    subtitle: Optional[str] = None
    body: str = ""


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


class SignoffView(BaseModel):
    """Eine Freigabe-Partei eines Dokuments (Anzeige im Auftrag / «Meine Dokumente»)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    signer_object_id: int
    signer_name: Optional[str] = None
    action: str = "sign"                      # confirm | sign
    order_index: int = 0
    status: str = "pending"                   # pending | signed | rejected
    signature_url: Optional[str] = None
    reason: Optional[str] = None
    acted_at: Optional[datetime] = None


class DocumentEmbed(BaseModel):
    """Eingebetteter Stand des Dokument-Schritts (im Auftrag).

    ``object_number`` (Instanz-Objektnummer) und ``document_date`` (Instanz-Freigabedatum)
    werden serverseitig aus der vom Auftrag erzeugten Instanz abgeleitet."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    done: bool = False                         # vollständig freigegeben (ausgestellt + alle signiert)
    issued: bool = False                       # Inhalt festgeschrieben (Unterschriften laufen)
    content: Optional[DocumentContent] = None
    object_number: Optional[int] = None       # = Instanz-Objektnummer (die Dokumentennummer)
    document_date: Optional[datetime] = None   # = instances.released_at
    created_by_name: Optional[str] = None
    # Freigabe-Parteien (endlich, gated den Abschluss) + Deklaration vom Schritt.
    signoffs: list[SignoffView] = []
    sign_sequential: bool = False
    visibility: str = "internal"


class SignerSubstitution(BaseModel):
    """Personal ersetzt eine deklarierte Freigabe-Partei am LAUFENDEN Auftrag (auditiert):
    das offene (pending/abgelehnte) Signoff wandert auf die neue Person – Reihenfolge-
    Position und Aktion (confirm/sign) bleiben; bereits geleistete Unterschriften nie."""

    old_signer_object_id: int
    new_signer_object_id: int
    step_id: Optional[int] = None              # Mehr-Operationen-Routing (mehrere Dokument-Schritte)


class SignoffAction(BaseModel):
    """Aktion einer Freigabe-Partei auf «ihr» Signoff (Unterschrift/Bestätigung/Ablehnung)."""

    action: str = "sign"                       # confirm | sign | reject | withdraw
    signature_url: Optional[str] = None        # Pflicht bei action='sign'
    reason: Optional[str] = None               # Grund bei action='reject'

    @field_validator("action")
    @classmethod
    def _action_ok(cls, v: str) -> str:
        if v not in ("confirm", "sign", "reject", "withdraw"):
            raise ValueError("action muss confirm, sign, reject oder withdraw sein")
        return v
