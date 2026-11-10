"""►►► **Eine Mail des Hauses hinausschicken – EINE Stelle.** ◄◄◄

Jede Mail, die das ERP an eine Person schickt – eine Antwort aus dem Verlauf, das Papier
eines Belegs, ein Dokument zum Unterschreiben, die Eingangsbestätigung, die Bitte um
Bestätigung des Newsletters –, entsteht hier, auf demselben Weg:

1. **Wer schreibt**: der Mensch, der sie auslöst (Personal) – sonst die Gesellschaft hinter
   dem Postfach. Nie der Admin, der das Postfach verbunden hat.
2. **Gebaut beim Anlegen, einmal** (``build``): Vorlage, Unterschrift, Fuss. Was im Verlauf
   steht, ist ab diesem Augenblick, was hinausgeht – der Versand baut nichts mehr.
3. **Zum Versand gegeben** (``outgoing``): sie geht hinaus, oder sie wartet auf ihr Postfach,
   bis es verbunden ist – nie steht sie still als «gesendet» da. Einen dritten Weg gibt es nicht.

Die Gesellschaft, wie sie in Unterschrift und Fuss steht, kommt aus ``firm`` – ebenfalls
nur hier.
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..core import clock
from ..domain import communication as dc
from ..domain import policy
from ..models import Message, MessageParty, UserProfile
from . import mail_layout as layout


def firm(db: Session, channel: str) -> layout.Firm:
    """Die Gesellschaft hinter einem Postfach – mit seiner Adresse und seinem Bild; ist es
    nicht verbunden, mit ihrer Kontakt-E-Mail."""
    from . import mailbox
    box = mailbox.active(db, channel)
    company = mailbox.company(db, channel)
    address = box.address if box is not None else ((company.email or "") if company else "")
    return layout.firm_of(company, address, (box.picture or "") if box is not None else "")


def signer(db: Session, msg: Message) -> Optional[layout.Signer]:
    """Wer unterschreibt: der Mensch, der die Mail **geschrieben** hat (``created_by``),
    sofort erkennbar als Mitarbeiter – mit seinem Profilbild. Eine automatische Mail
    unterschreibt das Unternehmen (``None``)."""
    if msg.created_by is None:
        return None
    person = db.query(UserProfile).filter(UserProfile.object_id == msg.sender_object_id).first()
    return layout.as_signer(person) if policy.is_staff(person) else None


def build(db: Session, msg: Message, *, kicker: str = "",
          extra: Optional[layout.Extra] = None) -> None:
    """►►► **Die Mail bauen – beim Anlegen, einmal.** ◄◄◄ Aus ihrem Text wird die Mail der
    einen Vorlage (``mail_layout.compose``): ``html`` ist, was hinausgeht, ``body`` der
    Inhalt, wie er im Verlauf steht – Wort für Wort. Ein Newsletter trägt den Abmeldelink
    seiner Empfängerin im Fuss."""
    unsubscribe = None
    if msg.newsletter:
        from .newsletter import footer
        to = db.query(MessageParty.object_id).filter(MessageParty.message_id == msg.id,
                                                     MessageParty.role == "to").scalar()
        unsubscribe = footer(to) if to else None
    mail = layout.compose(msg.subject or "", msg.body or "", firm(db, msg.channel),
                          signer(db, msg), kicker=kicker, extra=extra, unsubscribe=unsubscribe)
    msg.body, msg.html = mail.body, mail.html
    db.flush()


def deliver(db: Session, *, channel: str, to: list[int], subject: str, lead: str,
            author: Optional[UserProfile] = None, kicker: str = "",
            extra: Optional[layout.Extra] = None) -> Message:
    """**Eine Mail des Hauses an Personen** – anlegen, bauen, zum Versand geben. ``author``
    ist, wer sie auslöst; ist es kein Personal (ein Kunde auf seiner Seite, der Takt, die
    Website), schreibt die Gesellschaft."""
    from . import mailbox
    from .communication import write
    staff = author is not None and policy.is_staff(author) and author.object_id
    msg = Message(sender_object_id=author.object_id if staff else dc.company_of(channel),
                  channel=channel, subject=subject, body=lead, at=clock.utcnow(),
                  created_by=author.id if staff else None, outgoing=True)
    write(db, msg, {"to": to, "cc": [], "bcc": [], "about": []})
    build(db, msg, kicker=kicker, extra=extra)
    mailbox.send_after(db)
    return msg
