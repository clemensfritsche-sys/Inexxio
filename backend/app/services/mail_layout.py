"""►►► **Ein Brief – jeder Absender** (die eine Mail-Vorlage des Hauses). ◄◄◄

Jede Mail, die das ERP hinausschickt – von Hand geschrieben oder automatisch –, ist
dieselbe Hülle: **Kopf** (Logo, Stichwort) · **Überschrift** · **Inhalt** · **Unterschrift**
· **Fuss**. Nur der Inhalt wechselt. Gestaltet im Artefakt «INEXXIO E-Mail-Design».

►►► **Was im ERP steht, ist was hinausging – Wort für Wort.** ◄◄◄ ``compose`` baut aus
EINER Angabe (Text + Bausteine) alle drei Fassungen: den **Verlauf** (``Mail.body``, so
steht die Nachricht im ERP), den **Text** der Mail und ihr **HTML**. Eine zweite Stelle,
die den Inhalt zusammensetzt, wäre die, an der beide auseinanderlaufen – genau das ist
passiert: die Vorlage strich «Danke für Ihre Nachricht …» als vermeintliche Grussformel,
der Verlauf zeigte ihn. **Die Vorlage nimmt darum nie etwas weg**; steht schon ein Gruss
da, lässt sie nur ihren eigenen weg.

Die übrigen Regeln:

* **Die Überschrift ist der Betreff** – ohne «Re:» (``dc.title``).
* **Unterschrieben wird mit dem Menschen, im Namen des Unternehmens** – mit Bild daneben
  (sein Profilbild, sonst seine Initialen); eine automatische Mail unterschreibt das
  Unternehmen, mit dem Bild seines Postfachs. Telefon und E-Mail sind die der
  Gesellschaft – keine Funktion, keine Direktnummer, nie «Ihr Team».
* **Der Absendername folgt daraus**: «Clemens Fritsche · INEXXIO» bzw. «INEXXIO».
* **Keine Fläche hinter der Mail**: sie steht im Postfach wie jede andere Mail – eine
  getönte Bühne passt in kein Postfach, und im dunklen Modus schon gar nicht. Das Logo
  ist transparent (mit hellem Rand, damit es auch auf dunklem Grund lesbar bleibt), und
  wo der Client es kann, wechselt es auf die helle Fassung.

Das HTML ist **E-Mail-HTML** – Tabellen, Stile am Element, keine Webschrift, die man
braucht, Bilder als PNG. Daneben steht immer derselbe Inhalt als Text.
"""

import re
from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional
from urllib.parse import urlparse

from ..core.config import get_settings
from ..domain import communication as dc

BRAND = "INEXXIO"
LOGO, LOGO_DARK = "/mail/logo.png", "/mail/logo-dark.png"
LOGO_W, LOGO_H = 69, 26
GREETING = "Freundliche Grüsse"
FONT = "Inter, Arial, Helvetica, sans-serif"
INK, TEXT_2, TEXT_3, LINE = "#0A0A0B", "#45423D", "#6B6862", "#E4E2DE"
GREEN, RED_TEXT = "#1E7F46", "#C8140F"
#: Nur die Grussformel selbst – «Danke für Ihre Nachricht» ist Inhalt, kein Gruss.
_GREETING = re.compile(
    r"^(mit )?(freundlichen|herzlichen|besten|lieben|liebe|beste|viele|schöne|freundliche|"
    r"herzliche)?\s*(grüsse|grüße|gruss|gruß|grüssen|grüßen)\b|^(best|kind|warm) regards\b|"
    r"^regards\b", re.I)


@dataclass
class Firm:
    """Wer schreibt – die eigene Gesellschaft hinter dem Postfach."""
    name: str
    address: list[str] = field(default_factory=list)
    phone: str = ""             # zur Anzeige («+41 79 505 83 02»)
    tel: str = ""               # zum Wählen («+41795058302»)
    email: str = ""
    picture: str = ""           # das Bild des Postfachs (Google-Konto)


@dataclass
class Signer:
    """Der Mensch, der geschrieben hat."""
    name: str
    photo: str = ""


@dataclass
class Facts:
    """Eine Kopie dessen, was jemand geschickt hat: Angaben und die Nachricht selbst."""
    title: str
    rows: list[tuple[str, str]] = field(default_factory=list)
    message: str = ""


@dataclass
class Steps:
    """Was geschehen ist und was als Nächstes kommt."""
    title: str
    items: list[tuple[str, bool]] = field(default_factory=list)


@dataclass
class Extra:
    """Was eine automatische Mail zusätzlich trägt (die Eingangsbestätigung)."""
    facts: Optional[Facts] = None
    steps: Optional[Steps] = None
    #: Satz vor der Telefonnummer der Gesellschaft («Eilt es? Dann rufen Sie uns an:»).
    call: str = ""


@dataclass
class Mail:
    """Die drei Fassungen derselben Mail – gebaut an einer Stelle."""
    body: str       # so steht sie im Verlauf des ERP
    text: str       # Textfassung der Mail
    html: str       # HTML-Fassung der Mail


def firm_of(company: Any, mailbox_address: str, picture: str = "") -> Firm:
    """Die Gesellschaft, wie sie in Unterschrift und Fuss steht."""
    from . import address
    from . import phone as tel
    from .sites import legal_name
    if company is None:
        return Firm(name=BRAND, email=mailbox_address, picture=picture or "")
    e164 = tel.e164(company.phone, company.country) or ""
    return Firm(name=legal_name(company), address=address.lines(address.of_company(company)),
                phone=tel.display(company.phone, e164) or "", tel=e164,
                email=mailbox_address or company.email or "", picture=picture or "")


def sender_name(signer: Optional[Signer]) -> str:
    """Der Name im «Von» – der Mensch und die Marke, oder nur die Marke."""
    return f"{signer.name} · {BRAND}" if signer else BRAND


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]


def greeted(body: str) -> bool:
    """Steht am Schluss schon ein Gruss? Dann setzt die Vorlage keinen zweiten."""
    lines = [ln.strip() for ln in (body or "").split("\n") if ln.strip()]
    return any(len(ln) <= 40 and _GREETING.match(ln) for ln in lines[-3:])


# ---------------------------------------------------------------------------
# Die eine Zusammensetzung
# ---------------------------------------------------------------------------

def compose(subject: str, lead: str, firm: Firm, signer: Optional[Signer], *,
            kicker: str = "", extra: Optional[Extra] = None) -> Mail:
    """Aus EINER Angabe alle drei Fassungen – der Verlauf ist der Inhalt der Mail."""
    body = _content_text(lead, extra, firm)
    return Mail(body=body, text=text(subject, body, firm, signer),
                html=_html(subject, lead, firm, signer, kicker, extra))


def _content_text(lead: str, extra: Optional[Extra], firm: Firm) -> str:
    parts = ["\n\n".join(_paragraphs(lead))]
    if extra and extra.facts:
        f = extra.facts
        parts.append("\n".join([f.title, *(f"{k}: {v}" for k, v in f.rows),
                                *([f.message.strip()] if f.message.strip() else [])]))
    if extra and extra.steps:
        parts.append("\n".join([extra.steps.title, *(label for label, _ in extra.steps.items)]))
    if extra and extra.call and firm.phone:
        parts.append(f"{extra.call} {firm.phone}")
    return "\n\n".join(p for p in parts if p)


def _signature_lines(firm: Firm, signer: Optional[Signer], body: str) -> list[str]:
    reach = " · ".join(x for x in (firm.phone, firm.email) if x)
    return [*([] if greeted(body) else [GREETING]), *([signer.name] if signer else []),
            firm.name, *([reach] if reach else [])]


def text(subject: str, body: str, firm: Firm, signer: Optional[Signer]) -> str:
    foot = " · ".join([firm.name, *firm.address])
    return "\n".join([dc.title(subject), "", body, "", *_signature_lines(firm, signer, body),
                      "", "—", foot]).strip() + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _p(content: str, size: int = 16, color: str = INK, extra: str = "") -> str:
    return (f'<p style="margin:0 0 20px;font-family:{FONT};font-size:{size}px;'
            f'line-height:{size + 8}px;color:{color};{extra}">{content}</p>')


def _rich(par: str) -> str:
    """Ein Absatz: maskiert, Zeilenumbrüche bleiben, Adressen werden Links."""
    out = escape(par).replace("\n", "<br>")
    return re.sub(r"(https?://[^\s<]+)",
                  lambda m: f'<a href="{m.group(1)}" style="color:{INK}">{m.group(1)}</a>', out)


def _label(t: str) -> str:
    return (f'<p style="margin:0 0 10px;font-family:{FONT};font-size:12px;line-height:16px;'
            f'font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{TEXT_3}">'
            f'{escape(t)}</p>') if t else ""


def _box(inner: str) -> str:
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {LINE};border-radius:12px;border-collapse:separate;'
            f'margin:0 0 24px">{inner}</table>')


def _facts(f: Facts) -> str:
    cell = f"font-family:{FONT};padding:12px 20px;"
    rows = "".join(
        f'<tr><td style="{cell}border-bottom:1px solid {LINE};font-size:13px;color:{TEXT_3}">'
        f'{escape(k)}:</td><td align="right" style="{cell}border-bottom:1px solid {LINE};'
        f'font-size:14px;color:{INK}">{escape(v)}</td></tr>' for k, v in f.rows)
    msg = (f'<tr><td colspan="2" style="{cell}padding-top:14px;padding-bottom:14px;'
           f'font-size:14px;line-height:20px;color:{TEXT_2}">{_rich(f.message.strip())}</td>'
           f'</tr>' if f.message.strip() else "")
    return _label(f.title) + _box(rows + msg)


def _steps(s: Steps) -> str:
    dot = ("width:10px;height:10px;border-radius:10px;box-sizing:border-box;font-size:0;"
           "line-height:0")
    rows = []
    for i, (label, done) in enumerate(s.items):
        mark = f"background:{GREEN}" if done else f"border:2px solid {INK}"
        if i:
            rows.append(f'<tr><td style="padding:0 0 0 4px"><div style="width:2px;height:12px;'
                        f'background:{LINE};font-size:0;line-height:0"></div></td><td></td></tr>')
        rows.append(f'<tr><td width="22" valign="middle"><div style="{dot};{mark}"></div></td>'
                    f'<td style="font-family:{FONT};font-size:14px;line-height:22px;color:{INK}">'
                    f'{escape(label)}</td></tr>')
    return (_label(s.title) + '<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 24px">{"".join(rows)}</table>')


def _call(text: str, firm: Firm) -> str:
    if not (text and firm.phone):
        return ""
    link = (f'<a href="tel:{escape(firm.tel or firm.phone)}" style="color:{INK};font-weight:600;'
            f'text-decoration:none;white-space:nowrap">{escape(firm.phone)}</a>')
    return _box(f'<tr><td style="padding:16px 20px;font-family:{FONT};font-size:14px;'
                f'line-height:20px;color:{INK}">{escape(text)} {link}</td></tr>')


def _extra(x: Optional[Extra], firm: Firm) -> str:
    if x is None:
        return ""
    return ((_facts(x.facts) if x.facts else "") + (_steps(x.steps) if x.steps else "")
            + _call(x.call, firm))


def _initials(name: str) -> str:
    return "".join(w[0] for w in name.split()[:2]).upper()


def _avatar(firm: Firm, signer: Optional[Signer]) -> str:
    """Das Bild neben der Unterschrift – Profilbild, Postfach-Bild oder Initialen."""
    pic = (signer.photo if signer else firm.picture) or ""
    if pic:
        return (f'<img src="{escape(pic)}" width="48" height="48" alt="" style="display:block;'
                f'width:48px;height:48px;border-radius:24px;border:0">')
    if signer is None:
        return ""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0"><tr><td width="48" '
            f'height="48" align="center" valign="middle" style="width:48px;height:48px;'
            f'border-radius:24px;background:{INK};color:#FFFFFF;font-family:{FONT};'
            f'font-size:16px;font-weight:600">{escape(_initials(signer.name))}</td></tr></table>')


def _signature(firm: Firm, signer: Optional[Signer], body: str) -> str:
    reach = " · ".join(x for x in (
        f'<a href="tel:{escape(firm.tel or firm.phone)}" style="color:{TEXT_2};'
        f'text-decoration:none">{escape(firm.phone)}</a>' if firm.phone else "",
        f'<a href="mailto:{escape(firm.email)}" style="color:{TEXT_2};text-decoration:none">'
        f'{escape(firm.email)}</a>' if firm.email else "") if x)
    head = escape(signer.name) if signer else escape(firm.name)
    lines = [f'<span style="font-size:15px;line-height:20px;font-weight:600;color:{INK}">'
             f'{head}</span>', *([escape(firm.name)] if signer else []), *([reach] if reach else [])]
    avatar = _avatar(firm, signer)
    pic = (f'<td width="48" valign="middle" style="width:48px;padding:0 16px 0 0">{avatar}</td>'
           if avatar else "")
    greeting = "" if greeted(body) else _p(GREETING, extra="margin:8px 0 16px")
    return (greeting + f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>{pic}'
            f'<td valign="middle" style="font-family:{FONT};font-size:13px;line-height:18px;'
            f'color:{TEXT_2}">{"<br>".join(lines)}</td></tr></table>')


def _footer(firm: Firm) -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    host = urlparse(base).netloc or base
    first = " · ".join([f'<b style="font-weight:600;color:{TEXT_2}">{escape(firm.name)}</b>',
                        *(escape(a) for a in firm.address[:2])])
    second = " · ".join([*([escape(firm.phone)] if firm.phone else []),
                         f'<a href="{base}" style="color:{TEXT_3};text-decoration:none">'
                         f'{escape(host)}</a>'])
    return (f'<tr><td style="padding:24px 0 8px;border-top:1px solid {LINE};font-family:{FONT};'
            f'font-size:12px;line-height:18px;color:{TEXT_3}">{first}<br>{second}</td></tr>')


_DARK = ('<style>:root{color-scheme:light dark}'
         '@media (prefers-color-scheme:dark){.ix-logo-l{display:none!important}'
         '.ix-logo-d{display:block!important}}</style>')


def _logo(base: str) -> str:
    img = (f'width="{LOGO_W}" height="{LOGO_H}" alt="{BRAND}" style="display:block;'
           f'border:0;width:{LOGO_W}px;height:{LOGO_H}px')
    return (f'<img class="ix-logo-l" src="{base}{LOGO}" {img}">'
            f'<img class="ix-logo-d" src="{base}{LOGO_DARK}" {img};display:none">')


def _html(subject: str, lead: str, firm: Firm, signer: Optional[Signer], kicker: str,
          extra: Optional[Extra]) -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    pars = _paragraphs(lead)
    pre = escape((pars[0] if pars else "")[:140])
    kick = (f'<td align="right" valign="top" style="font-family:{FONT};font-size:12px;'
            f'line-height:16px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{RED_TEXT}">{escape(kicker)}</td>') if kicker else "<td></td>"
    content = "".join(_p(_rich(p)) for p in pars) + _extra(extra, firm)
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<title>{escape(dc.title(subject))}</title>{_DARK}</head><body style="margin:0;padding:0">'
        f'<span style="display:none;max-height:0;overflow:hidden;opacity:0">{pre}</span>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:600px"><tr><td style="padding:16px 8px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        f'<tr><td style="padding:0 0 28px"><table role="presentation" width="100%" '
        f'cellpadding="0" cellspacing="0"><tr><td valign="top">{_logo(base)}</td>{kick}'
        f'</tr></table></td></tr>'
        f'<tr><td style="padding:0 0 32px">'
        f'<h1 style="margin:0 0 20px;font-family:\'Inter Tight\',{FONT};font-size:28px;'
        f'line-height:34px;font-weight:700;letter-spacing:-0.02em;color:{INK}">'
        f'{escape(dc.title(subject))}</h1><!--inhalt-->{content}<!--/inhalt-->'
        f'{_signature(firm, signer, lead)}</td></tr>{_footer(firm)}'
        '</table></td></tr></table></body></html>')
