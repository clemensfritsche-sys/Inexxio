"""►►► **Der Anmeldelink – im Kleid des Hauses.** ◄◄◄

Wer sich mit seiner E-Mail anmeldet, bekommt einen Link. Firebase könnte ihn selbst schicken –
von einer fremden Adresse, im Kleid von Google. Hier schickt ihn **das Haus**: derselbe Link
(Firebase erzeugt ihn, ``generate_sign_in_with_email_link``), aber in der einen Mail-Vorlage
(``mail_layout.compose``), aus dem Postfach der Gesellschaft zum Land des Besuchers
(``newsletter.sending_channel``) – wie die Bitte um Bestätigung des Newsletters.

**Nichts scheitert still, nichts hängt daran**: ist kein Postfach verbunden oder geht die Mail
nicht hinaus, sagt ``send`` ``False`` – dann schickt die Oberfläche den Link wie bisher über
Firebase (``frontend/src/lib/firebase.sendMagicLink``). Angelegt wird nichts: kein Verlauf, keine
Person – die Person entsteht wie immer bei der ersten Anmeldung (``core/auth``).
"""

from firebase_admin import auth as firebase_auth
from sqlalchemy.orm import Session

from ..core import report
from ..core.config import get_settings
from . import mail_layout

WORDS = {
    "subject": "Ihr Anmeldelink für INEXXIO",
    "kicker": "Anmelden",
    "lead": "Guten Tag\n\nMit dem Knopf unten melden Sie sich bei INEXXIO an – ohne Passwort. "
            "Der Link gilt eine Stunde und nur ein einziges Mal.",
    "button": "Jetzt anmelden",
    "note": "Sie haben keinen Link angefordert? Dann löschen Sie diese Mail einfach – ohne den "
            "Klick geschieht nichts.",
}


def continue_url() -> str:
    """Wohin der Link führt – immer die eigene Seite, nie eine Adresse aus der Anfrage."""
    return f"{get_settings().frontend_base_url.rstrip('/')}/login/verify"


def make_link(email: str) -> str:
    """Der Anmeldelink, wie ihn Firebase selbst verschicken würde."""
    from ..core.auth import _init_firebase
    _init_firebase()
    settings = firebase_auth.ActionCodeSettings(url=continue_url(), handle_code_in_app=True)
    return firebase_auth.generate_sign_in_with_email_link(email, settings)


def compose(db: Session, channel: str, link: str) -> mail_layout.Mail:
    """Die Mail: Überschrift, zwei Sätze, ein Knopf – unterschrieben von der Gesellschaft."""
    from . import outbox
    action = mail_layout.Action(title="", text="", label=WORDS["button"], url=link,
                                note=WORDS["note"])
    return mail_layout.compose(WORDS["subject"], WORDS["lead"], outbox.firm(db, channel), None,
                               kicker=WORDS["kicker"], extra=mail_layout.Extra(action=action))


def send(db: Session, email: str, country: str | None = None) -> bool:
    """►► Den Anmeldelink im Kleid des Hauses schicken. ``False`` = nicht hinausgegangen
    (kein Postfach, Firebase oder Gmail nicht erreichbar) – die Oberfläche nimmt dann den Weg
    über Firebase. ◄◄"""
    from . import mailbox
    from .newsletter import sending_channel
    channel = sending_channel(db, country)
    if channel is None:
        return False
    try:
        link = make_link(email)
    except Exception as exc:  # Firebase nicht erreichbar oder Adresse abgewiesen
        report.warn(f"LOGIN link not generated: {type(exc).__name__}")
        return False
    return mailbox.send_direct(db, channel, email, WORDS["subject"], compose(db, channel, link))
