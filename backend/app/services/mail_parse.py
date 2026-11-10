"""►►► **Eine Mail von Gmail lesen – ohne Netz, ohne Datenbank.** ◄◄◄

Was ``mailbox`` aus einer Gmail-Nachricht macht: der Text (``_text``, HTML zu Text, Zitate weg –
``_strip_quote``), die Anhänge (``_attachments``), ob es Massenpost ist (``_bulk``), was nie
gelesen wird (``NEVER``). Reine Funktionen – darum auch einzeln prüfbar.
"""

import base64
import re
from html.parser import HTMLParser
from typing import Any


MAX_BODY = 20_000


#: Nie abgleichen: Entwürfe, Spam, Papierkorb.
NEVER = {"DRAFT", "SPAM", "TRASH"}


#: Was Gmail selbst als Massenpost einordnet – von aussen kommend legt es keine Kontakte an.
BULK_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES",
               "CATEGORY_FORUMS"}


_ROBOT = re.compile(r"(no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce)", re.I)


def _bulk(labels: set[str], head: dict[str, str], addr: str) -> bool:
    """Massenpost legt keine Kontakte an: Gmails eigene Einordnung, die üblichen Köpfe
    automatischer Mails, und Absender, die niemand liest."""
    auto = head.get("auto-submitted", "no").lower()
    return bool(labels & BULK_LABELS or "list-unsubscribe" in head
                or head.get("precedence", "").lower() in {"bulk", "list", "junk"}
                or auto != "no" or _ROBOT.search(addr.split("@")[0]))


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("style", "script"):
            self.skip += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("style", "script") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(data)


def _decode(part: dict[str, Any]) -> str:
    data = (part.get("body") or {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out = [payload]
    for p in payload.get("parts") or []:
        out += _parts(p)
    return out


def _text(payload: dict[str, Any]) -> str:
    """Der lesbare Text: ``text/plain`` zuerst, sonst ``text/html`` ohne Auszeichnung."""
    parts = [p for p in _parts(payload) if not p.get("filename")]
    for mime in ("text/plain", "text/html"):
        for p in parts:
            if p.get("mimeType") == mime and (text := _decode(p)):
                if mime == "text/html":
                    h = _Html()
                    h.feed(text)
                    text = "".join(h.out)
                return re.sub(r"\n{3,}", "\n\n", text.replace("\r", "")).strip()
    return ""


#: Wo das Zitat beginnt: «Am … schrieb …:» (Gmail, Apple), «-----Ursprüngliche Nachricht-----»,
#: und der Kopf, den Outlook über das Zitat setzt («Von: … / Gesendet: …», auch englisch,
#: oft nach einer Linie aus Unterstrichen).
_QUOTE = re.compile(
    r"\n[ \t]*(?:(?:Am|On)\b[^\n]*(?:\n[^\n]*)?(?:schrieb|wrote)[^\n]*:[ \t]*\n"
    r"|-{2,}[ \t]*(?:Original Message|Ursprüngliche Nachricht)[ \t]*-{2,}"
    r"|_{10,}[ \t]*\n"
    r"|\*?(?:Von|From):\*?[ \t][^\n]*\n(?:[^\n]*\n){0,2}?[ \t]*\*?(?:Gesendet|Sent|Datum|Date):)",
    re.I)


def _strip_quote(text: str) -> str:
    """Ohne den zitierten Verlauf – der steht schon als eigene Nachricht im Verlauf."""
    m = _QUOTE.search("\n" + text + "\n")
    if m and m.start() > 0:
        text = text[: m.start() - 1]
    lines = text.rstrip().split("\n")
    while lines and lines[-1].lstrip().startswith(">"):
        lines.pop()
    return "\n".join(lines).strip()


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Name, Grösse, Sorte und wo der Teil in Gmail steht – die Datei selbst bleibt dort und
    wird erst geholt, wenn ein Mensch sie öffnet (``attachment``)."""
    return [{"name": p["filename"], "size": (p.get("body") or {}).get("size", 0),
             "mime": p.get("mimeType") or "", "part": p.get("partId")}
            for p in _parts(payload) if p.get("filename")]
