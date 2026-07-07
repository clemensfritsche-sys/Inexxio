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


class AcknowledgeRequest(BaseModel):
    kind: str
