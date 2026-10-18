"""►►► **Ein Brief – jeder Absender** (die eine Mail-Vorlage des Hauses). ◄◄◄

Jede Mail, die das ERP hinausschickt – von Hand geschrieben oder automatisch –, ist
dieselbe Hülle: **Kopf** (Logo, Stichwort) · **Überschrift** · **Inhalt** · **Unterschrift**
· **Fuss**. Nur der Inhalt wechselt. Gestaltet im Artefakt «INEXXIO E-Mail-Design».

Vier Regeln, und jede steht hier:

* **Die Überschrift ist der Betreff** – ohne «Re:» (``dc.title``). Eine zweite, erfundene
  Überschrift wäre eine zweite Aussage über dasselbe Anliegen.
* **Unterschrieben wird mit dem Menschen, im Namen des Unternehmens**: der Name dessen,
  der geschrieben hat, darunter die Gesellschaft mit **ihrer** Telefonnummer und **ihrer**
  E-Mail – keine Funktion, keine Direktnummer, nie «Ihr Team». Was niemand geschrieben
  hat (eine automatische Bestätigung), trägt keinen Namen.
* **Der Absendername folgt daraus**: «Clemens Fritsche · INEXXIO» bzw. «INEXXIO»
  (``sender_name``) – die Adresse bleibt die des Postfachs, Antworten landen im ERP.
* **Der Fuss sind zwei leise Zeilen**: wer wir sind, wie man uns erreicht.

Das HTML ist **E-Mail-HTML** – Tabellen, Stile am Element, keine Webschrift, die man
braucht (Gmail zeigt Inter nicht; Arial ist erlaubt), das Logo als PNG. Daneben steht
immer derselbe Inhalt als Text.
"""

import re
from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional
from urllib.parse import urlparse

from ..core.config import get_settings
from ..domain import communication as dc

BRAND = "INEXXIO"
LOGO = "/logo/inexxio-ehemals-hs-steiner.png"
GREETING = "Freundliche Grüsse"
FONT = "Inter, Arial, Helvetica, sans-serif"
INK, TEXT_2, TEXT_3, LINE, SOFT, STAGE = (
    "#0A0A0B", "#45423D", "#6B6862", "#E4E2DE", "#F7F6F4", "#EFEEEB")
GREEN, RED_TEXT = "#1E7F46", "#C8140F"


@dataclass
class Firm:
    """Wer schreibt – die eigene Gesellschaft hinter dem Postfach."""
    name: str
    address: list[str] = field(default_factory=list)
    phone: str = ""
    email: str = ""


@dataclass
class Extra:
    """Was eine automatische Mail zusätzlich trägt (die Eingangsbestätigung)."""
    copy_title: str = ""
    copy: list[tuple[str, str]] = field(default_factory=list)
    quote: str = ""
    steps: list[tuple[str, bool]] = field(default_factory=list)
    note: str = ""


def firm_of(company: Any, mailbox_address: str) -> Firm:
    """Die Gesellschaft, wie sie in Unterschrift und Fuss steht."""
    from . import address
    from .sites import legal_name
    if company is None:
        return Firm(name=BRAND, email=mailbox_address)
    return Firm(name=legal_name(company), address=address.lines(address.of_company(company)),
                phone=company.phone or "", email=mailbox_address or company.email or "")


def sender_name(signer: Optional[str]) -> str:
    """Der Name im «Von» – der Mensch und die Marke, oder nur die Marke."""
    return f"{signer} · {BRAND}" if signer else BRAND


def without_closing(body: str) -> str:
    """Der Text ohne eine selbst getippte Grussformel am Schluss – die Unterschrift setzt
    die Vorlage, zweimal «Freundliche Grüsse» wäre einmal zu viel."""
    lines = (body or "").rstrip().split("\n")
    filled = [i for i, ln in enumerate(lines) if ln.strip()]
    for i in filled[-4:]:
        if dc._CLOSING.match(lines[i].strip()):
            return "\n".join(lines[:i]).rstrip()
    return (body or "").strip()


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]


def text(subject: str, body: str, firm: Firm, signer: Optional[str]) -> str:
    """Die Mail als Text – derselbe Inhalt wie das HTML, für jedes Programm lesbar."""
    sign = [GREETING, *([signer] if signer else []), firm.name,
            " · ".join(x for x in (firm.phone, firm.email) if x)]
    foot = " · ".join([firm.name, *firm.address])
    return "\n".join([dc.title(subject), "", without_closing(body), "", "", *sign,
                      "", "—", foot]).strip() + "\n"


def _p(content: str, size: int = 16, color: str = INK, extra: str = "") -> str:
    return (f'<p style="margin:0 0 20px;font-family:{FONT};font-size:{size}px;'
            f'line-height:{size + 8}px;color:{color};{extra}">{content}</p>')


def _rich(par: str) -> str:
    """Ein Absatz: maskiert, Zeilenumbrüche bleiben, Adressen werden Links."""
    out = escape(par).replace("\n", "<br>")
    return re.sub(r"(https?://[^\s<]+)",
                  lambda m: f'<a href="{m.group(1)}" style="color:{INK}">{m.group(1)}</a>', out)


def _extra(x: Optional[Extra]) -> str:
    if x is None:
        return ""
    parts = []
    if x.copy or x.quote:
        rows = "".join(
            f'<tr><td style="padding:12px 20px;border-bottom:1px solid {LINE};font-family:{FONT};'
            f'font-size:13px;color:{TEXT_3}">{escape(k)}</td><td align="right" style="padding:12px '
            f'20px;border-bottom:1px solid {LINE};font-family:{FONT};font-size:14px;color:{INK}">'
            f'{escape(v)}</td></tr>' for k, v in x.copy)
        quote = (f'<tr><td colspan="2" style="padding:14px 20px;background:{SOFT};font-family:'
                 f'{FONT};font-size:14px;line-height:20px;color:{TEXT_2}">«{_rich(x.quote)}»</td>'
                 f'</tr>' if x.quote else "")
        parts.append(_label(x.copy_title) + f'<table role="presentation" width="100%" '
                     f'cellpadding="0" cellspacing="0" style="border:1px solid {LINE};'
                     f'border-radius:12px;border-collapse:separate;overflow:hidden;'
                     f'margin:0 0 24px">{rows}{quote}</table>')
    if x.steps:
        dots = "".join(
            f'<tr><td width="22" valign="middle" style="padding:4px 0"><div style="width:10px;'
            f'height:10px;border-radius:10px;{"background:" + GREEN if done else "border:2px solid " + INK};'
            f'box-sizing:border-box"></div></td><td style="padding:4px 0;font-family:{FONT};'
            f'font-size:14px;line-height:22px;color:{INK}">{escape(label)}</td></tr>'
            for label, done in x.steps)
        parts.append(f'<table role="presentation" cellpadding="0" cellspacing="0" '
                     f'style="margin:0 0 24px">{dots}</table>')
    if x.note:
        parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                     f'style="margin:0 0 24px"><tr><td style="padding:16px 20px;background:{SOFT};'
                     f'border-radius:12px;font-family:{FONT};font-size:14px;line-height:20px;'
                     f'color:{INK}">{_rich(x.note)}</td></tr></table>')
    return "".join(parts)


def _label(t: str) -> str:
    return (f'<p style="margin:0 0 10px;font-family:{FONT};font-size:12px;line-height:16px;'
            f'font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{TEXT_3}">'
            f'{escape(t)}</p>') if t else ""


def _signature(firm: Firm, signer: Optional[str]) -> str:
    reach = " · ".join(escape(x) for x in (firm.phone, firm.email) if x)
    name = (f'<span style="font-size:15px;line-height:20px;font-weight:600;color:{INK}">'
            f'{escape(signer)}</span><br>') if signer else ""
    return (_p(GREETING, extra="margin:8px 0 12px") +
            f'<p style="margin:0;font-family:{FONT};font-size:13px;line-height:19px;'
            f'color:{TEXT_2}">{name}{escape(firm.name)}<br>{reach}</p>')


def _footer(firm: Firm) -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    host = urlparse(base).netloc or base
    first = " · ".join([f'<b style="font-weight:600;color:{TEXT_2}">{escape(firm.name)}</b>',
                        *(escape(a) for a in firm.address[:2])])
    second = " · ".join([*([escape(firm.phone)] if firm.phone else []),
                         f'<a href="{base}" style="color:{TEXT_3};text-decoration:none">'
                         f'{escape(host)}</a>'])
    return (f'<tr><td align="center" style="padding:20px 40px 28px;border-top:1px solid {LINE};'
            f'font-family:{FONT};font-size:12px;line-height:18px;color:{TEXT_3}">{first}<br>'
            f'{second}</td></tr>')


def html(subject: str, body: str, firm: Firm, signer: Optional[str], *,
         kicker: str = "", extra: Optional[Extra] = None) -> str:
    """Die Mail als E-Mail-HTML – die Vorlage aus dem Design-Artefakt."""
    base = get_settings().frontend_base_url.rstrip("/")
    pars = _paragraphs(without_closing(body))
    pre = escape((pars[0] if pars else "")[:140])
    kick = (f'<td align="right" valign="top" style="font-family:{FONT};font-size:12px;'
            f'line-height:16px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{RED_TEXT}">{escape(kicker)}</td>') if kicker else "<td></td>"
    content = "".join(_p(_rich(p)) for p in pars)
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" '
        f'content="light"><title>{escape(dc.title(subject))}</title></head>'
        f'<body style="margin:0;padding:0;background:{STAGE}">'
        f'<span style="display:none;max-height:0;overflow:hidden;opacity:0">{pre}</span>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="background:{STAGE}"><tr><td align="center" style="padding:24px 12px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px;background:#FFFFFF;border:1px solid {LINE};border-radius:12px;'
        f'border-collapse:separate">'
        f'<tr><td style="padding:28px 40px 0"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0"><tr><td valign="top"><img src="{base}{LOGO}" '
        f'width="96" height="48" alt="{BRAND}" style="display:block;border:0"></td>{kick}'
        f'</tr></table></td></tr>'
        f'<tr><td style="padding:24px 40px 36px">'
        f'<h1 style="margin:0 0 20px;font-family:\'Inter Tight\',{FONT};font-size:28px;'
        f'line-height:34px;font-weight:700;letter-spacing:-0.02em;color:{INK}">'
        f'{escape(dc.title(subject))}</h1>{content}{_extra(extra)}'
        f'{_signature(firm, signer)}</td></tr>{_footer(firm)}'
        '</table></td></tr></table></body></html>')
