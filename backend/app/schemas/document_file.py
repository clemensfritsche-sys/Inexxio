from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Analyse (KI-Vorschlag) ────────────────────────────────────────────────────────

class SuggestedLink(BaseModel):
    object_id: int
    object_type: Optional[str] = None
    label: str
    relation: str = "about"
    score: float = 0.0


class DocumentAnalyzeResponse(BaseModel):
    """Ergebnis der Analyse – ein bearbeitbarer Vorschlag (noch NICHT gespeichert)."""
    action_id: Optional[int] = None
    title: Optional[str] = None
    doc_type: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None
    byte_size: Optional[int] = None
    page_count: Optional[int] = None
    ai_analyzed: bool = False
    extracted_data: Optional[dict] = None
    suggested_links: list[SuggestedLink] = []
    # Dublette: dieselbe Datei ist bereits abgelegt (Hash-Treffer).
    duplicate: bool = False
    duplicate_object_id: Optional[int] = None


# ── Bestätigung (Mensch prüft Name + Zuordnung) ──────────────────────────────────

class DocumentLinkInput(BaseModel):
    object_id: int
    relation: str = "about"
    primary: bool = False


class DocumentConfirmRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    doc_type: str = "other"
    # Mindestens EINE Objektzuordnung – ein Dokument darf nie objektlos entstehen.
    links: list[DocumentLinkInput] = Field(min_length=1)


# ── Anzeige (Reiter «Dokumente» je Objekt) ───────────────────────────────────────

class ObjectDocument(BaseModel):
    """Ein Dokument im Reiter «Dokumente» eines Objekts. Vereint zwei Quellen:
    ``kind='file'`` = hochgeladenes Fremd-Dokument, ``kind='generated'`` = im
    Prozessschritt «Dokument» erzeugtes Inexxio-Dokument."""
    kind: str                      # 'file' | 'generated'
    id: int                        # document_files.id  ODER  documents.id
    object_number: Optional[int] = None
    title: str
    doc_type: Optional[str] = None
    summary: Optional[str] = None
    mime: Optional[str] = None
    filename: Optional[str] = None
    page_count: Optional[int] = None
    byte_size: Optional[int] = None
    download_url: str
    relation: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by_name: Optional[str] = None
