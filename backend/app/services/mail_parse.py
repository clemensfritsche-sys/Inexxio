"""►►► **Eine Mail von Gmail lesen – ohne Netz, ohne Datenbank.** ◄◄◄

Was ``mailbox`` aus einer Gmail-Nachricht macht: der Text (``_text``, HTML zu Text, Zitate weg –
``_strip_quote``), die Anhänge (``_attachments``), ob es Massenpost ist (``_bulk``), was nie
gelesen wird (``NEVER``). Reine Funktionen – darum auch einzeln prüfbar.
"""

import base64
import re
from dataclasses import dataclass
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any, Optional

from ..domain import communication as dc


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
        self.quote: list[str] = []               # was wegfiel – das Zitat, als Text

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
            if tag in ("br", "p", "div", "tr", "li"):
                self.quote.append("\n")
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
            if tag in ("br", "p", "div", "tr", "li"):
                self.quote.append("\n")
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
        if self.skip:
            return
        (self.quote if (self.stopped or self.hide_from is not None) else self.out).append(data)


def _html_text(html: str) -> tuple[str, bool, str]:
    """Text eines HTML-Teils, ob ein markiertes Zitat wegfiel, und das Zitat als Text."""
    h = _Html()
    h.feed(html)
    h.close()
    return "".join(h.out), h.quoted, "".join(h.quote)


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


@dataclass
class Bounce:
    """Eine Unzustellbar-Meldung: welche unserer Mails, an wen, warum."""
    original: str           # die ``Message-ID`` unserer Mail
    recipients: str         # an wen sie nicht ging
    reason: str             # der Satz des empfangenden Servers (gekürzt)


_ID = re.compile(r"<[^<>\s]+@[^<>\s]+>")
_DIAG = re.compile(r"^Diagnostic-Code:\s*(?:smtp;\s*)?(.+)$", re.I | re.M)
_STATUS = re.compile(r"^Status:\s*(.+)$", re.I | re.M)


def bounce(payload: dict[str, Any], head: dict[str, str]) -> Optional[Bounce]:
    """►►► **Ein Rückläufer – erkannt an seiner Form, zugeordnet über unsere Kennung.** ◄◄◄

    Eine Unzustellbar-Meldung (RFC 3464: ``multipart/report`` mit ``delivery-status``, oder
    ``X-Failed-Recipients``, oder ein Absender wie ``mailer-daemon``) trägt die Kopfzeilen der
    Mail, die nicht ankam. Gesucht wird darin **eine Kennung, die das ERP vergeben hat**
    (``communication.ours``) – sonst ist es kein Rückläufer einer unserer Mails (``None``)."""
    ctype = head.get("content-type", "").lower()
    sender = parseaddr(head.get("from", ""))[1].split("@")[0]
    if not ("delivery-status" in ctype or "x-failed-recipients" in head
            or re.search(r"mailer-daemon|postmaster", sender, re.I)):
        return None
    texts, ids = [], [head.get("references", ""), head.get("in-reply-to", "")]
    for part in _parts(payload):
        ids += [h.get("value", "") for h in part.get("headers") or []
                if h.get("name", "").lower() in {"message-id", "references", "in-reply-to"}]
        if part.get("mimeType", "").startswith(("text/", "message/")):
            texts.append(_decode(part))
    ids += [m for t in texts for m in re.findall(r"^Message-ID:\s*(<[^>]+>)", t, re.I | re.M)]
    original = next((m for raw in ids for m in _ID.findall(raw) if dc.ours(m)), None)
    if original is None:
        return None
    found = re.findall(r"^Final-Recipient:\s*(?:rfc822;\s*)?(\S+)", "\n".join(texts), re.I | re.M)
    recipients = head.get("x-failed-recipients", "") or ", ".join(dict.fromkeys(found))
    diag = _DIAG.search("\n".join(texts)) or _STATUS.search("\n".join(texts))
    reason = " ".join((diag.group(1) if diag else "").split())[:300]
    return Bounce(original=original, recipients=recipients.strip()[:300], reason=reason)


def _tidy(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.replace("\r", "").replace("\xa0", " ")).strip()


def _text(payload: dict[str, Any]) -> str:
    """►►► **Der lesbare Text – ohne Zitat, wo das Mailprogramm es markiert hat.** ◄◄◄ Trägt
    der HTML-Teil ein Zitat-Zeichen (``QUOTE_CLASSES`` · ``QUOTE_STOPS``), gilt sein Text ohne
    das Zitat; sonst der Text-Teil wie bisher (und ``_strip_quote`` sucht das Zitat an seinen
    Mustern – der Rückfall für Mails ohne Zeichen)."""
    return text_and_quote(payload)[0]


def text_and_quote(payload: dict[str, Any]) -> tuple[str, str]:
    """►►► **Der Text und das Zitat – getrennt, nichts geht verloren.** ◄◄◄ Der Text ist, was
    der Verlauf zeigt (ohne Zitat); das Zitat ist, was darunter stand – bei einer Weiterleitung
    die eigentliche Sache («Anfrage von Helvetia»). Es steht zugeklappt an der Mail
    (``messages.quote``), und die KI liest es mit."""
    parts = [p for p in _parts(payload) if not p.get("filename")]
    html = next((t for p in parts if p.get("mimeType") == "text/html" and (t := _decode(p))), "")
    plain = next((t for p in parts if p.get("mimeType") == "text/plain" and (t := _decode(p))), "")
    if html:
        cleaned, quoted, quote = _html_text(html)
        if quoted:
            return _strip_quote(_tidy(cleaned)), _tidy(quote)
        if not plain:
            plain = cleaned
    head, quote = split_quote(_tidy(plain))
    return head, quote


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


def split_quote(text: str) -> tuple[str, str]:
    """Der Text ohne den zitierten Verlauf – und das Zitat (an seinen Mustern, ``_QUOTE``,
    oder an den Zeilen mit «>» am Schluss)."""
    quote = ""
    m = _QUOTE.search("\n" + text + "\n")
    if m and m.start() > 0:
        text, quote = text[: m.start() - 1], text[m.start() - 1:]
    lines = text.rstrip().split("\n")
    tail: list[str] = []
    while lines and lines[-1].lstrip().startswith(">"):
        tail.insert(0, lines.pop())
    if tail:
        quote = "\n".join([*tail, quote]).strip()
    return "\n".join(lines).strip(), quote.strip()


def _strip_quote(text: str) -> str:
    """Ohne den zitierten Verlauf – der steht schon als eigene Nachricht im Verlauf."""
    return split_quote(text)[0]


def _attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Name, Grösse, Sorte und wo der Teil in Gmail steht – die Datei selbst bleibt dort und
    wird erst geholt, wenn ein Mensch sie öffnet (``attachment``)."""
    return [{"name": p["filename"], "size": (p.get("body") or {}).get("size", 0),
             "mime": p.get("mimeType") or "", "part": p.get("partId")}
            for p in _parts(payload) if p.get("filename")]
