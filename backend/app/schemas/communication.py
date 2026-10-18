"""Kommunikation – was hinein- und was herausgeht (``services/communication``)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PersonRef(BaseModel):
    """Eine beteiligte Person – Nummer, Name und ob sie zu **uns** gehört."""

    object_id: int
    name: str = ""
    staff: bool = False
    #: Die Firma, für die sie auftritt («Muster AG») – im Kopf **vor** dem Namen.
    company: Optional[str] = None
    #: Ihre Adresse – nur im Hover; im Kopf steht nie eine E-Mail-Adresse.
    email: Optional[str] = None


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
    #: Für wen das Postfach steht – die Gesellschaft («Inexxio AG») bzw. der Mitarbeiter
    #: hinter einem persönlichen. Ein Verlauf nennt damit nie eine nackte Adresse.
    name: Optional[str] = None


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
    Angaben. Ohne Text braucht sie einen Betreff – das ist «erledigt ohne Antwort» für
    dieses Anliegen."""

    channel: str
    #: Kein ``sender``: geschrieben wird **immer im eigenen Namen** – der Absender ist, wer
    #: angemeldet ist. Ein trotzdem gesendeter Wert wird verworfen.
    to: list[int] = Field(default_factory=list)
    cc: list[int] = Field(default_factory=list)
    bcc: list[int] = Field(default_factory=list)
    about: list[int] = Field(default_factory=list)
    subject: Optional[str] = Field(None, max_length=255)
    body: str = Field("", max_length=20000)
    #: Leer heisst «jetzt»; in der Zukunft ist es eine Erinnerung bzw. später gesendet.
    at: Optional[datetime] = None
    #: **Nur bei einem Gespräch** (``live``): «wurde angerufen» – dann ist der Kontakt im
    #: «An» der Absender und ich der Empfänger. Ein Anruf hält fest, was passiert ist; wer
    #: ihn erfasst hat, steht weiterhin in ``created_by``. Bei jedem anderen Kanal 400.
    incoming: bool = False


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
    #: Die Signatur einer Mail, abgetrennt vom Text (``domain.split_signature``) – die
    #: Oberfläche klappt sie ein. Leer = keine erkannt.
    signature: Optional[str] = None
    at: datetime
    #: **Das Anliegen** – der Betreff ohne «Re:»/«AW:» (``domain.title``). Gleiches
    #: Anliegen, gleiche Farbe; eine Antwort erledigt alle offenen davon.
    topic: str = ""
    #: Der Betreff einer Antwort auf DIESE Nachricht – fest, «Re: » davor wie Gmail.
    reply_subject: str = ""
    #: «Allen antworten»: Absender, An und Cc dieser Nachricht (``communication.reply_all``).
    #: Die Oberfläche belegt damit vor; nur der Absender lässt sich nicht entfernen.
    reply_all: list[PersonRef] = []
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
