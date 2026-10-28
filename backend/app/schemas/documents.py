"""Dokumente – was über die API-Grenze geht (``services/documents``)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentRefOut(BaseModel):
    id: int
    object_id: int
    #: Typ des Datensatzes (``user`` · ``order`` · …) und sein Name.
    type: Optional[str] = None
    label: str
    part: Optional[str] = None
    #: Gesetzt bei einem Pflichtfeld: was auf dem Schloss steht. Dann gibt es kein ×.
    field: Optional[str] = None
    field_label: Optional[str] = None


class SignatureOut(BaseModel):
    id: int
    person_object_id: int
    name: str
    signed_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    reason: Optional[str] = None


class DocumentSummary(BaseModel):
    """Eine Zeile im Feed bzw. eine Kachel unten im Datensatz."""
    object_id: int
    art: str
    name: str
    status: str
    source: str
    mime: str
    created_at: datetime
    #: Das kleine Bild der ersten Seite (abgeleitet) – leer, wenn es keins gibt.
    preview_url: Optional[str] = None
    #: Wo das Gesuchte im gelesenen Text steht (nur bei einer Suche).
    snippet: Optional[str] = None


class DocumentDetail(DocumentSummary):
    file_url: Optional[str] = None
    filename: Optional[str] = None
    byte_size: int = 0
    pages: Optional[int] = None
    refs: list[DocumentRefOut] = []
    created_by: Optional[str] = None
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    delete_reason: Optional[str] = None
    #: Warum «Löschen» (noch) nicht geht – leer heisst: es geht. ``can`` als Satz.
    delete_problem: Optional[str] = None
    signatures: list[SignatureOut] = []
    #: Ist die Datei ein Papier aus unserer Vorlage (Beleg, Verfasstes)? Dann zeigt die
    #: Seite es als HTML in einem abgeschirmten Rahmen.
    html: Optional[str] = None


class FiledOut(BaseModel):
    """Die Antwort auf «Freigeben»: das Dokument – und ob es dieselbe Datei schon gab."""
    document: DocumentDetail
    existed: bool = False


class RefIn(BaseModel):
    object_id: int


class DeleteIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class RecordOut(BaseModel):
    """Ein Datensatz zum Referenzieren – «Typ · Name» mit Nummer."""
    object_id: int
    type: str
    label: str
