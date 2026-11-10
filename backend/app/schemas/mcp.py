"""Die Seite «Claude verbinden» und meine Verbindungen (``routers/mcp``)."""

from datetime import datetime

from pydantic import BaseModel


class AskOut(BaseModel):
    """Welcher Claude-Client verbunden werden will – und wohin er zurückkehrt."""
    client: str
    host: str
    #: Die volle Adresse, an die der Code geht – die Person sieht, wohin sie ihn gibt.
    redirect: str


class ApproveIn(BaseModel):
    r: str
    allow: bool


class ApproveOut(BaseModel):
    """Die Adresse zurück zum Client (mit Code oder Absage)."""
    redirect: str


class GrantOut(BaseModel):
    """Eine offene Verbindung mit Claude – je erlaubtem Client eine (``mcp.grants``)."""
    id: int
    #: Erlaubt am.
    at: datetime
    #: Zuletzt benutzt (Erlauben oder jüngste Erneuerung) – älter als 30 Tage ist sie nicht offen.
    used: datetime
    client: str
