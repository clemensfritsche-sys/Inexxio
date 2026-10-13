"""►►► **Kommunikation – alles ist eine Nachricht** (CRM Schritt 2). ◄◄◄

Drei Regeln, eine Logik, keine Sonderfälle:

1. **Alles ist eine Nachricht.** E-Mail, Anruf, Notiz, interne Frage, Rundmail,
   Erinnerung und «erledigt ohne Antwort» sind dasselbe Objekt – sie unterscheiden sich
   allein darin, welche Angaben gesetzt sind (Kanal · An/Cc/Bcc · Betrifft · Zeitpunkt ·
   Antwort auf). Kein Typfeld und keine Fallunterscheidung nach der Art.
2. **Der Verlauf einer Person** = jede Nachricht, an der sie beteiligt ist (Absender,
   An, Cc, Bcc, Betrifft), chronologisch. Der Verlauf einer **Firma** ist der ihrer
   Personen – sie spiegelt, sie schreibt nicht.
3. **Offen** = eine Nachricht **an uns**, deren Zeitpunkt erreicht ist und auf die noch
   keine Nachricht antwortet. **Überfällig** nach ``OVERDUE_AFTER``, rund um die Uhr,
   intern wie extern gleich.

**Ein Kanal ist ein Katalogeintrag, kein Datensatz**: ein neuer Kanal ist eine Zeile
hier. Er gehört dem Betreiber (der eigenen Gesellschaft, die die Website vertritt);
persönliche Postfächer eines Mitarbeiters haben dieselbe Form (``u<Objektnummer>``).
Zwei Eigenschaften tragen die ganze Unterscheidung:

* ``outside`` – verlässt die Nachricht das Haus? (Intern: nie.)
* ``live`` – beantwortet sich das Gespräch selbst? Ein Anruf ist ein Gespräch, beide
  waren dabei; danach wartet niemand auf eine Antwort. Wer zurückrufen muss, setzt eine
  Erinnerung – ebenfalls eine Nachricht.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

#: Ab wann eine offene Nachricht als überfällig gilt – rund um die Uhr.
OVERDUE_AFTER = timedelta(hours=2)

#: Die Rollen eines Beteiligten. ``about`` («betrifft») macht eine Nachricht im Verlauf
#: einer Person sichtbar, an der sie weder schreibt noch liest – die Notiz über sie, die
#: interne Frage zu ihr.
ROLES = ("to", "cc", "bcc", "about")


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    #: ``email`` · ``phone`` · ``internal`` – bestimmt allein das Symbol.
    kind: str
    address: Optional[str]
    outside: bool
    live: bool


#: Der Kanal des Unternehmens: seine Adresse ist die **Kontakt-E-Mail des Betreibers**
#: (``company_settings.email``) – keine zweite Angabe, die beim Domain-Wechsel stehenbleibt.
COMPANY_MAIL = "info"

CHANNELS: dict[str, Channel] = {
    c.key: c for c in (
        Channel(COMPANY_MAIL, "Unternehmen", "email", None, outside=True, live=False),
        Channel("phone", "Telefon", "phone", None, outside=True, live=True),
        Channel("intern", "Intern", "internal", None, outside=False, live=False),
    )
}

#: Ein **persönliches Postfach** eines Mitarbeiters ist ein Kanal derselben Form –
#: Schlüssel ``u<Objektnummer>``. Kein Katalogeintrag je Person: die Form ist die Regel.
PERSONAL_PREFIX = "u"


def personal(object_id: int) -> str:
    return f"{PERSONAL_PREFIX}{object_id}"


def owner_of(key: str) -> Optional[int]:
    """Die Objektnummer hinter einem persönlichen Postfach – sonst ``None``."""
    rest = key[len(PERSONAL_PREFIX):] if key.startswith(PERSONAL_PREFIX) else ""
    return int(rest) if rest.isdigit() else None


def channel(key: str) -> Channel:
    """Der Kanal zu einem Schlüssel – ein unbekannter ist ein Fehler, kein Rückfall."""
    if key in CHANNELS:
        return CHANNELS[key]
    if owner_of(key) is not None:
        return Channel(key, "Persönlich", "email", None, outside=True, live=False)
    raise ValueError(f"Kanal «{key}» gibt es nicht.")


def is_mail(key: str) -> bool:
    """Geht dieser Kanal über ein Postfach? (Info oder persönlich)"""
    return key == COMPANY_MAIL or owner_of(key) is not None


def to_us(*, channel_key: str, sender_staff: bool, to_staff: bool) -> bool:
    """**Ist diese Nachricht an UNS gerichtet?** – die eine Frage hinter «offen».

    Uns = jeder Kanal der eigenen Gesellschaft und jeder Mitarbeiter. Also: wer von
    aussen schreibt, schreibt an uns; und wer intern einen Mitarbeiter im «An» nennt
    (auch sich selbst – das ist die Erinnerung), ebenso. Ein Gespräch (``live``)
    wartet auf niemanden."""
    if channel(channel_key).live:
        return False
    return (not sender_staff) or to_staff
