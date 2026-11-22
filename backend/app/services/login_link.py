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

LANGS = ("de", "fr", "en", "it")
"""Die Sprachen der Anmeldung – dieselben wie die der Website (``website/src/config/languages.mjs``)."""

WORDS = {
    "de": {
        "subject": "Ihr Anmeldelink für INEXXIO",
        "kicker": "Anmelden",
        "lead": "Guten Tag\n\nMit dem Knopf unten melden Sie sich bei INEXXIO an – ohne Passwort. "
                "Der Link gilt eine Stunde und nur ein einziges Mal.",
        "button": "Jetzt anmelden",
        "note": "Sie haben keinen Link angefordert? Dann löschen Sie diese Mail einfach – ohne den "
                "Klick geschieht nichts.",
    },
    "fr": {
        "subject": "Votre lien de connexion INEXXIO",
        "kicker": "Se connecter",
        "lead": "Bonjour\n\nLe bouton ci-dessous vous connecte à INEXXIO – sans mot de passe. "
                "Le lien est valable une heure et une seule fois.",
        "button": "Se connecter maintenant",
        "note": "Vous n'avez pas demandé de lien ? Supprimez simplement ce message – sans clic, "
                "rien ne se passe.",
    },
    "en": {
        "subject": "Your INEXXIO sign-in link",
        "kicker": "Sign in",
        "lead": "Hello\n\nThe button below signs you in to INEXXIO – no password needed. "
                "The link is valid for one hour and can be used only once.",
        "button": "Sign in now",
        "note": "Didn't ask for a link? Simply delete this email – nothing happens without the click.",
    },
    "it": {
        "subject": "Il suo link di accesso a INEXXIO",
        "kicker": "Accedere",
        "lead": "Buongiorno\n\nCon il pulsante qui sotto accede a INEXXIO – senza password. "
                "Il link vale un'ora e una sola volta.",
        "button": "Accedere ora",
        "note": "Non ha richiesto alcun link? Cancelli semplicemente questa e-mail – senza il clic "
                "non succede nulla.",
    },
}


def continue_url(lang: str = "de") -> str:
    """Wohin der Link führt – immer die eigene Seite, nie eine Adresse aus der Anfrage; die Sprache
    steht immer darin (vor dem ``lang``, das Firebase selbst anhängt)."""
    return f"{get_settings().frontend_base_url.rstrip('/')}/login/verify?lang={lang}"


def make_link(email: str, lang: str = "de") -> str:
    """Der Anmeldelink, wie ihn Firebase selbst verschicken würde."""
    from ..core.auth import _init_firebase
    _init_firebase()
    settings = firebase_auth.ActionCodeSettings(url=continue_url(lang), handle_code_in_app=True)
    return firebase_auth.generate_sign_in_with_email_link(email, settings)


def compose(db: Session, channel: str, link: str, lang: str = "de") -> mail_layout.Mail:
    """Die Mail: Überschrift, zwei Sätze, ein Knopf – unterschrieben von der Gesellschaft."""
    from . import outbox
    w = WORDS[lang]
    action = mail_layout.Action(title="", text="", label=w["button"], url=link, note=w["note"])
    return mail_layout.compose(w["subject"], w["lead"], outbox.firm(db, channel), None,
                               kicker=w["kicker"], extra=mail_layout.Extra(action=action))


def send(db: Session, email: str, country: str | None = None, lang: str = "de") -> bool:
    """►► Den Anmeldelink im Kleid des Hauses schicken. ``False`` = nicht hinausgegangen
    (kein Postfach, Firebase oder Gmail nicht erreichbar) – die Oberfläche nimmt dann den Weg
    über Firebase. ◄◄"""
    from . import mailbox
    from .newsletter import sending_channel
    channel = sending_channel(db, country)
    if channel is None:
        return False
    try:
        link = make_link(email, lang)
    except Exception as exc:  # Firebase nicht erreichbar oder Adresse abgewiesen
        report.warn(f"LOGIN link not generated: {type(exc).__name__}")
        return False
    return mailbox.send_direct(db, channel, email, WORDS[lang]["subject"], compose(db, channel, link, lang))
