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
persönliche Adressen eines Mitarbeiters wären ein weiterer Eintrag mit derselben Form.
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


CHANNELS: dict[str, Channel] = {
    c.key: c for c in (
        Channel("info", "info@inexxio.com", "email", "info@inexxio.com",
                outside=True, live=False),
        Channel("phone", "Telefon", "phone", None, outside=True, live=True),
        Channel("intern", "Intern", "internal", None, outside=False, live=False),
    )
}


def channel(key: str) -> Channel:
    """Der Kanal zu einem Schlüssel – ein unbekannter ist ein Fehler, kein Rückfall."""
    if key not in CHANNELS:
        raise ValueError(f"Kanal «{key}» gibt es nicht.")
    return CHANNELS[key]


def to_us(*, channel_key: str, sender_staff: bool, to_staff: bool) -> bool:
    """**Ist diese Nachricht an UNS gerichtet?** – die eine Frage hinter «offen».

    Uns = jeder Kanal der eigenen Gesellschaft und jeder Mitarbeiter. Also: wer von
    aussen schreibt, schreibt an uns; und wer intern einen Mitarbeiter im «An» nennt
    (auch sich selbst – das ist die Erinnerung), ebenso. Ein Gespräch (``live``)
    wartet auf niemanden."""
    if channel(channel_key).live:
        return False
    return (not sender_staff) or to_staff
