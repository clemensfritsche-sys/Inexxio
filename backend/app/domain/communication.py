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
hier. Postfächer haben eine **Form** statt einer Zeile: jede **eigene Gesellschaft** hat
eines (``c<Objektnummer>``, seine Adresse ist ihre Kontakt-E-Mail – dieselbe, die die
Website je Besucherland zeigt), jeder Mitarbeiter ein persönliches (``u<Objektnummer>``).
Zwei Eigenschaften tragen die ganze Unterscheidung:

* ``outside`` – verlässt die Nachricht das Haus? (Intern: nie.)
* ``live`` – beantwortet sich das Gespräch selbst? Ein Anruf ist ein Gespräch, beide
  waren dabei; danach wartet niemand auf eine Antwort. Wer zurückrufen muss, setzt eine
  Erinnerung – ebenfalls eine Nachricht.
"""

import re
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
        Channel("phone", "Telefon", "phone", None, outside=True, live=True),
        Channel("intern", "Intern", "internal", None, outside=False, live=False),
    )
}

#: Ein **Postfach** ist ein Kanal einer festen Form – kein Katalogeintrag je Gesellschaft
#: oder Person: die Form ist die Regel. ``c`` = eigene Gesellschaft, ``u`` = Mitarbeiter.
COMPANY_PREFIX = "c"
PERSONAL_PREFIX = "u"


def company(object_id: int) -> str:
    return f"{COMPANY_PREFIX}{object_id}"


def personal(object_id: int) -> str:
    return f"{PERSONAL_PREFIX}{object_id}"


def _number(key: str, prefix: str) -> Optional[int]:
    rest = key[len(prefix):] if key.startswith(prefix) else ""
    return int(rest) if rest.isdigit() else None


def company_of(key: str) -> Optional[int]:
    """Die Gesellschaft hinter einem Unternehmens-Postfach – sonst ``None``."""
    return _number(key, COMPANY_PREFIX)


def owner_of(key: str) -> Optional[int]:
    """Die Objektnummer hinter einem persönlichen Postfach – sonst ``None``."""
    return _number(key, PERSONAL_PREFIX)


def channel(key: str) -> Channel:
    """Der Kanal zu einem Schlüssel – ein unbekannter ist ein Fehler, kein Rückfall."""
    if key in CHANNELS:
        return CHANNELS[key]
    if company_of(key) is not None:
        return Channel(key, "Unternehmen", "email", None, outside=True, live=False)
    if owner_of(key) is not None:
        return Channel(key, "Persönlich", "email", None, outside=True, live=False)
    raise ValueError(f"Kanal «{key}» gibt es nicht.")


def is_mail(key: str) -> bool:
    """Geht dieser Kanal über ein Postfach? (Gesellschaft oder persönlich)"""
    return company_of(key) is not None or owner_of(key) is not None


def info_repair_sql() -> list[str]:
    """Der frühere eine Unternehmens-Kanal ``info`` wird der des **Betreibers** – gelesen
    von Migration 146 **und** vom Lifespan-Netz (die dev-Datenbank fährt keine Migration,
    #778). Selbstbegrenzend: danach gibt es kein ``info`` mehr."""
    op = ("(SELECT 'c' || object_id FROM company_settings WHERE is_own AND object_id "
          "IS NOT NULL ORDER BY is_operator DESC, id LIMIT 1)")
    return [f"UPDATE {t} SET channel = {op} WHERE channel = 'info' AND {op} IS NOT NULL"
            for t in ("messages", "mailboxes")]


def contact_repair_sql() -> list[str]:
    """**Die Kontakt-E-Mail einer eigenen Gesellschaft IST die Adresse ihres Postfachs**
    – wo eines verbunden ist und beide auseinanderliegen (vor der Kopplung liess sich ein
    anderes Konto verbinden), gewinnt das Postfach. Gelesen von Migration 147 **und** vom
    Lifespan-Netz. Selbstbegrenzend: danach stimmen beide überein."""
    return ["UPDATE company_settings AS c SET email = m.address FROM mailboxes AS m "
            "WHERE m.is_active AND c.is_own AND c.object_id IS NOT NULL "
            "AND m.channel = 'c' || c.object_id AND c.email IS DISTINCT FROM m.address"]


def to_us(*, channel_key: str, sender_staff: bool, to_staff: bool) -> bool:
    """**Ist diese Nachricht an UNS gerichtet?** – die eine Frage hinter «offen».

    Uns = jeder Kanal der eigenen Gesellschaft und jeder Mitarbeiter. Also: wer von
    aussen schreibt, schreibt an uns; und wer intern einen Mitarbeiter im «An» nennt
    (auch sich selbst – das ist die Erinnerung), ebenso. Ein Gespräch (``live``)
    wartet auf niemanden."""
    if channel(channel_key).live:
        return False
    return (not sender_staff) or to_staff


# ---------------------------------------------------------------------------
# Die Signatur einer Mail
# ---------------------------------------------------------------------------

#: Grussformeln, nach denen nur noch der Name steht – und dann die Signatur.
_CLOSING = re.compile(
    r"^(mit )?(freundlichen|herzlichen|besten|lieben|liebe|beste|viele|schöne|"
    r"freundliche|herzliche)?\s*(grüsse|grüße|gruss|gruß|grüssen|grüßen)\b|"
    r"^(best|kind|warm)( regards| wishes)?\b|^regards\b|^cheers\b|^thanks\b|"
    r"^danke\b|^merci\b", re.I)
#: Mehr Zeilen hat keine Signatur – darüber ist es Inhalt, der nicht verschwinden darf.
SIGNATURE_MAX = 16


def _lines(text: str) -> list[str]:
    return [ln.rstrip() for ln in text.replace("\r", "").split("\n")]


def tidy(text: str) -> str:
    """Leerzeilen zusammenfassen: höchstens eine zwischen zwei Absätzen."""
    return re.sub(r"\n[ \t]*(?:\n[ \t]*)+\n", "\n\n", "\n".join(_lines(text))).strip()


def split_signature(text: str, sender: str = "") -> tuple[str, Optional[str]]:
    """►►► **Text und Signatur – getrennt, damit die Signatur einklappen kann.** ◄◄◄

    Drei Merkmale, in dieser Reihenfolge, und jedes nur im Schluss der Mail
    (``SIGNATURE_MAX`` Zeilen): der Trenner ``--`` (RFC 3676), eine Grussformel mit dem
    Namen darunter, oder der Name des Absenders allein auf einer Zeile. **Gruss und Name
    bleiben stehen** – sie gehören zur Nachricht; eingeklappt wird, was danach kommt
    (Firma, Anschrift, Telefon, Links). Findet sich nichts, bleibt der Text, wie er ist:
    lieber eine Signatur zu viel zeigen als einen Satz verschlucken."""
    lines = _lines(tidy(text))
    filled = [i for i, ln in enumerate(lines) if ln.strip()]
    tail = filled[-SIGNATURE_MAX:] if len(filled) > 2 else []
    cut = _cut(lines, tail, sender)
    if cut is None:
        return "\n".join(lines), None
    body, sig = "\n".join(lines[:cut]).strip(), "\n".join(
        ln for ln in lines[cut:] if ln.strip() and ln.strip() not in ("--", "-- "))
    if not body or not sig or len(sig.split("\n")) < 2:
        return "\n".join(lines), None
    return body, sig


def _cut(lines: list[str], tail: list[int], sender: str) -> Optional[int]:
    """Die erste Zeile der Signatur – oder ``None``."""
    for i in tail:
        if lines[i].strip() == "--":
            return i
    name = re.sub(r"\s+", " ", sender).strip().lower()
    for i in reversed(tail):
        line = lines[i].strip()
        if len(line) <= 40 and _CLOSING.match(line):
            after = [j for j in tail if j > i]
            # Gruss + Name bleiben; was danach kommt, ist die Signatur.
            return after[1] if len(after) > 2 else None
    for i in tail[:-1]:
        if name and len(name) > 3 and lines[i].strip().lower() == name:
            return i + 1
    return None
