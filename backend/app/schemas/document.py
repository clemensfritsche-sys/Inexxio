"""Schemas für das Prozessschrittmodul «Dokument».

``DocumentContent`` ist die gemeinsame, bewusst schlanke Struktur eines „Word"-artigen
Textdokuments (Titel + nummerierte Abschnitte). Sie lebt an ZWEI Orten mit demselben
Format: editierbar auf der **Vorlage** (``ArticleProcessStep.document_content``) und – bei
der Auftragsfreigabe eingefroren – als Snapshot auf dem erzeugten **Dokument** (``Document``).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentSection(BaseModel):
    """Ein Abschnitt: Überschrift (z. B. «§1 Geltungsbereich») + Fliesstext (mehrzeilig)."""
    heading: str = ""
    body: str = ""


class DocumentContent(BaseModel):
    """Inhalt eines Dokuments – Titel/Untertitel/Datum + geordnete Abschnitte."""
    title: str = ""
    subtitle: Optional[str] = None
    document_date: Optional[str] = None   # Anzeige-Datum (frei), z. B. «Gültig ab 01.01.2027»
    sections: list[DocumentSection] = []


class DocumentEmbed(BaseModel):
    """Eingebetteter Stand des Dokument-Schritts (im Auftrag).

    Das Dokument trägt – anders als die kaufmännischen Fachzeilen – eine **eigene
    Objektnummer** (``object_id``) und den eingefrorenen Inhalt (``content``)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = 0
    object_id: Optional[int] = None
    done: bool = False
    title: Optional[str] = None
    content: Optional[DocumentContent] = None
    version: int = 1
    issued_at: Optional[datetime] = None
    created_by_name: Optional[str] = None


class DocumentResponse(BaseModel):
    """Standalone-Ansicht eines eingefrorenen Dokuments (ERP-Detail / Web-View)."""

    model_config = ConfigDict(from_attributes=True)

    object_id: Optional[int] = None
    order_object_id: Optional[int] = None
    article_object_id: Optional[int] = None
    title: Optional[str] = None
    content: Optional[DocumentContent] = None
    version: int = 1
    issued_at: Optional[datetime] = None
    created_at: datetime
