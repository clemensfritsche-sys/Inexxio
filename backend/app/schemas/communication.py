"""Kommunikation – was hinein- und was herausgeht (``services/communication``)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonRef(BaseModel):
    """Eine beteiligte Person – Nummer, Name und ob sie zu **uns** gehört."""

    object_id: int
    name: str = ""
    staff: bool = False


class ChannelOut(BaseModel):
    key: str
    label: str
    #: ``email`` · ``phone`` · ``internal`` – bestimmt allein das Symbol.
    kind: str
    outside: bool
    #: Ein Postfach (Unternehmen oder persönlich)? Dann ist ``label`` seine Adresse.
    mail: bool = False
    #: Ein persönliches Postfach? Dann schreibt nur sein Besitzer darüber.
    personal: bool = False


class Attachment(BaseModel):
    name: str
    size: int = 0
    #: Liegt die Datei bei uns (ein Bild aus dem Anfrage-Formular), ihre Adresse – sonst
    #: liegt sie in Gmail, und der Weg dorthin ist ``gmail_url``.
    url: Optional[str] = None


class MailboxOut(BaseModel):
    """Ein Postfach – das einer eigenen Gesellschaft oder das eigene des Betrachters."""

    channel: str
    address: str
    connected: bool
    #: Warum der Abgleich nicht geht (z. B. «Verbindung abgelaufen») – leer = in Ordnung.
    problem: Optional[str] = None
    may_connect: bool = False


class SyncOut(BaseModel):
    new: int


class MessageIn(BaseModel):
    """**Eine neue Nachricht.** Alle Arten haben dieselbe Form; was sie ist, sagen die
    Angaben. Ohne Text braucht sie ein «Antwort auf» – das ist «erledigt ohne Antwort»."""

    channel: str
    sender: int
    to: list[int] = Field(default_factory=list)
    cc: list[int] = Field(default_factory=list)
    bcc: list[int] = Field(default_factory=list)
    about: list[int] = Field(default_factory=list)
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field("", max_length=20000)
    #: Leer heisst «jetzt»; in der Zukunft ist es eine Erinnerung bzw. später gesendet.
    at: Optional[datetime] = None
    reply_to: list[int] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: int
    channel: ChannelOut
    sender: PersonRef
    to: list[PersonRef] = []
    cc: list[PersonRef] = []
    bcc: list[PersonRef] = []
    about: list[PersonRef] = []
    subject: Optional[str] = None
    body: str = ""
    at: datetime
    reply_to: list[int] = []
    #: Von uns geschrieben (rechts) ↔ von aussen (links).
    ours: bool
    #: An uns gerichtet und noch ohne Antwort, Zeitpunkt erreicht.
    open: bool = False
    overdue: bool = False
    #: Der Zeitpunkt liegt in der Zukunft («geplant»).
    planned: bool = False
    #: Eine Mail von uns, die noch nicht hinaus ist (geplant oder Versand gescheitert).
    pending: bool = False
    #: Anhänge – nur Name und Grösse; die Datei liegt in Gmail.
    attachments: list[Attachment] = []
    #: Wo die Mail in Gmail steht (nur für eine abgeglichene bzw. gesendete).
    gmail_url: Optional[str] = None


class OpenCount(BaseModel):
    """Wie viele offene Nachrichten im Verlauf dieser Person stehen."""

    object_id: int
    open: int
    overdue: int
