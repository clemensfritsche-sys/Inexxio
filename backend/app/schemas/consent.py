from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .document import DocumentContent


class PendingDocument(BaseModel):
    """Ein noch zu bestätigendes Dokument für den aktuellen Nutzer (Consent-Gate)."""

    kind: str                                   # agb | datenschutz | …
    title: str                                  # Anzeigename (Dokument-Titel bzw. Label)
    object_number: Optional[int] = None         # Version = Objektnummer der Dokument-Instanz
    document_date: Optional[datetime] = None
    content: Optional[DocumentContent] = None    # zum Rendern (DocumentView)


class MySignoffDocument(BaseModel):
    """Ein Dokument, auf das ICH als **Freigabe-Partei** noch handeln muss («Meine Dokumente»)."""

    signoff_id: int
    title: str
    object_number: Optional[int] = None
    document_date: Optional[datetime] = None
    action: str = "sign"                         # confirm | sign
    status: str = "pending"                      # pending | rejected
    actionable: bool = True                      # bin ich JETZT an der Reihe (sequenziell)?
    content: Optional[DocumentContent] = None


class AcknowledgeRequest(BaseModel):
    kind: str
    object_number: Optional[int] = None   # bei kind='document' (Publikums-Dokument) die Version


class Acknowledgement(BaseModel):
    """Eine erfolgte Bestätigung (für den Benutzer-ERP-Datensatz)."""

    kind: str
    title: str
    version_object_id: int          # Stand = Objektnummer der bestätigten Dokument-Instanz
    accepted_at: datetime
