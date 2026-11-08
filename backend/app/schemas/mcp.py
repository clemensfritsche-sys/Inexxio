"""Die Seite «Claude verbinden» und meine Verbindungen (``routers/mcp``)."""

from datetime import datetime

from pydantic import BaseModel


class AskOut(BaseModel):
    """Welcher Claude-Client verbunden werden will – und wohin er zurückkehrt."""
    client: str
    host: str


class ApproveIn(BaseModel):
    r: str
    allow: bool


class ApproveOut(BaseModel):
    """Die Adresse zurück zum Client (mit Code oder Absage)."""
    redirect: str


class GrantOut(BaseModel):
    """Eine Verbindung mit Claude – je erlaubtem Client eine."""
    id: int
    at: datetime
    client: str
