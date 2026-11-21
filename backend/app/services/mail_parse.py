"""►►► **Eine Mail von Gmail lesen – ohne Netz, ohne Datenbank.** ◄◄◄

Was ``mailbox`` aus einer Gmail-Nachricht macht: der Text (``_text``, HTML zu Text, Zitate weg –
``_strip_quote``), die Anhänge (``_attachments``), ob es Massenpost ist (``_bulk``), was nie
gelesen wird (``NEVER``). Reine Funktionen – darum auch einzeln prüfbar.
"""

import base64
import re
from html.parser import HTMLParser
from typing import Any, Optional


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


#: ►►► **Wo ein Mailprogramm das Zitat markiert** – im HTML-Teil, dasselbe Zeichen, nach dem
#: Gmail die «…» einklappt. ◄◄◄ Ein Element mit diesem Zeichen fällt samt Inhalt weg
#: (Gmail ``gmail_quote``, Apple ``blockquote type=cite``, Thunderbird ``moz-cite-prefix``,
#: Yahoo ``yahoo_quoted``); bei Outlook beginnt mit dem Kopf das Zitat, und alles danach fällt
#: weg (``divRplyFwdMsg``, ``appendonsend``, ``OutlookMessageHeader``).
QUOTE_CLASSES = ("gmail_quote", "moz-cite-prefix", "yahoo_quoted")
QUOTE_STOPS = ("divrplyfwdmsg", "appendonsend", "outlookmessageheader")
_VOID = {"br", "img", "hr", "meta", "input", "link", "col", "area", "base", "wbr", "source"}


class _Html(HTMLParser):
    """HTML zu Text – ohne Stil und Skript, und **ohne das Zitat**, wo das Mailprogramm es
    markiert hat (``quoted`` sagt, ob es eines fand)."""

    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0
        self.open: list[str] = []
        self.hide_from: Optional[int] = None     # Tiefe des Zitat-Elements, das gerade wegfällt
        self.stopped = False                     # ab hier ist alles Zitat (Outlook)
        self.quoted = False

    @staticmethod
    def _marks(tag: str, attrs: Any) -> tuple[bool, bool]:
        a = {k.lower(): (v or "") for k, v in attrs}
        names = (a.get("class", "") + " " + a.get("id", "")).lower()
        stop = any(m in names for m in QUOTE_STOPS)
        hide = (any(c in names.split() for c in QUOTE_CLASSES)
                or (tag == "blockquote" and a.get("type", "").lower() == "cite"))
        return hide, stop

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if self.stopped:
            return
        hide, stop = self._marks(tag, attrs)
        if stop:
            self.stopped = self.quoted = True
            return
        if tag not in _VOID:
            self.open.append(tag)
            if hide and self.hide_from is None:
                self.hide_from, self.quoted = len(self.open), True
        if self.hide_from is not None:
            return
        if tag in ("style", "script"):
            self.skip += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.stopped or tag in _VOID:
            return
        if tag in self.open:        # schliesst auch, was das HTML offen liess
            while self.open:
                if self.open.pop() == tag:
                    break
        if self.hide_from is not None and len(self.open) < self.hide_from:
            self.hide_from = None
            return
        if self.hide_from is None and tag in ("style", "script") and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not (self.skip or self.stopped or self.hide_from is not None):
            self.out.append(data)


def _html_text(html: str) -> tuple[str, bool]:
    """Text eines HTML-Teils und ob ein markiertes Zitat wegfiel."""
    h = _Html()
    h.feed(html)
    h.close()
    return "".join(h.out), h.quoted


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
    """►►► **Der lesbare Text – ohne Zitat, wo das Mailprogramm es markiert hat.** ◄◄◄ Trägt
    der HTML-Teil ein Zitat-Zeichen (``QUOTE_CLASSES`` · ``QUOTE_STOPS``), gilt sein Text ohne
    das Zitat; sonst der Text-Teil wie bisher (und ``_strip_quote`` sucht das Zitat an seinen
    Mustern – der Rückfall für Mails ohne Zeichen)."""
    parts = [p for p in _parts(payload) if not p.get("filename")]
    html = next((t for p in parts if p.get("mimeType") == "text/html" and (t := _decode(p))), "")
    plain = next((t for p in parts if p.get("mimeType") == "text/plain" and (t := _decode(p))), "")
    text = plain
    if html:
        cleaned, quoted = _html_text(html)
        if quoted or not plain:
            text = cleaned
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r", "").replace("\xa0", " ")).strip()


#: Wo das Zitat beginnt: «Am … schrieb …:» (Gmail, Apple – auch umbrochen, wenn Name und
#: Adresse lang sind), «-----Ursprüngliche Nachricht-----»,
#: und der Kopf, den Outlook über das Zitat setzt («Von: … / Gesendet: …», auch englisch,
#: oft nach einer Linie aus Unterstrichen).
_QUOTE = re.compile(
    r"\n[ \t]*(?:(?:Am|On)\b[^\n]*(?:\n[^\n]*){0,2}?(?:schrieb|wrote)[^\n]*(?:\n[^\n]*){0,2}?:[ \t]*\n"
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
