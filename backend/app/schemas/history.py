"""Der Verlauf eines Datensatzes (``services/history``) – eine Seite, die neuesten zuerst."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from .communication import MessageOut


class FieldChange(BaseModel):
    """``feld: alt → neu`` – roh, der Feldname bleibt, wie er in der Tabelle heisst. Bei einer
    neuen Zeile fehlt ``old``, bei einer gelöschten ``new``."""

    field: str
    old: Optional[str] = None
    new: Optional[str] = None


class LogRow(BaseModel):
    """Eine Zeile des Logs: eine geänderte Tabellenzeile oder ein Ereignis."""

    #: ``insert`` · ``update`` · ``delete`` · ``event``.
    action: str
    #: Die Tabelle, roh (``user_profiles``) – und ihr Wort («Person», ``domain/log.TABLE_WORDS``).
    table: Optional[str] = None
    word: Optional[str] = None
    row: Optional[str] = None
    #: Nur bei einem Ereignis: sein Name (``process.pass``, ``document.read`` …).
    event: Optional[str] = None
    changes: list[FieldChange] = []
    #: Die einfachen Angaben eines Ereignisses (Text, Zahl, ja/nein) – roh.
    payload: dict[str, str] = {}


class ChangeBlock(BaseModel):
    """**Eine Handlung** (``request_id``) – wer, woher, und was sich änderte."""

    #: ``person`` · ``ai`` · ``system`` · ``external``.
    actor_kind: str
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    source: str
    rows: list[LogRow] = []


class DocumentEntry(BaseModel):
    """Ein Dokument, das an diesem Datensatz hängt (seine Referenz)."""

    object_id: int
    art: str
    name: str
    part: Optional[str] = None
    field: Optional[str] = None
    deleted: bool = False


class HistoryEntry(BaseModel):
    #: Der Platz des Eintrags in der Reihenfolge – als Cursor verwendbar.
    key: str
    kind: Literal["message", "document", "change"]
    at: datetime
    message: Optional[MessageOut] = None
    document: Optional[DocumentEntry] = None
    change: Optional[ChangeBlock] = None


class HistoryPage(BaseModel):
    #: Die neuesten zuerst.
    entries: list[HistoryEntry] = []
    #: Der Cursor für die nächste (ältere) Seite – leer, wenn nichts mehr kommt.
    before: Optional[str] = None
