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
* **Eine Spalte, mittig, umrandet von einer Haarlinie** – weiss, keine Fläche dahinter
  und keine darin: gruppiert wird mit einer Linie. Eine getönte Bühne passt in kein
  Postfach, und im dunklen Modus schon gar nicht. Wo der Client den dunklen Modus meldet,
  tragen dieselben Elemente die dunkle Palette (``_DARK``); Gmail kehrt selbst um, darum
  ist das Logo transparent und hat einen hellen Rand.

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
LOGO_W, LOGO_H = 97, 26
GREETING = "Freundliche Grüsse"
FONT = "Inter, Arial, Helvetica, sans-serif"
INK, TEXT_2, TEXT_3, LINE = "#0A0A0B", "#44464A", "#66686D", "#E3E4E7"
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
class Action:
    """Der eine Klick, um den eine Mail bittet (Newsletter bestätigen) – ein Knopf, und
    in der Textfassung die Adresse dahinter."""
    title: str
    text: str
    label: str
    url: str
    #: Leise unter dem Knopf («Waren Sie das nicht? …»).
    note: str = ""


@dataclass
class Extra:
    """Was eine automatische Mail zusätzlich trägt (die Eingangsbestätigung)."""
    facts: Optional[Facts] = None
    steps: Optional[Steps] = None
    #: Satz vor der Telefonnummer der Gesellschaft («Eilt es? Dann rufen Sie uns an:»).
    call: str = ""
    action: Optional[Action] = None


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

@dataclass
class Unsubscribe:
    """Der Abmeldelink eines Newsletters – im Fuss, nie im Inhalt."""
    text: str       # «Sie erhalten … weil Sie sich angemeldet haben.»
    label: str      # «Abmelden»
    url: str


def compose(subject: str, lead: str, firm: Firm, signer: Optional[Signer], *,
            kicker: str = "", extra: Optional[Extra] = None,
            unsubscribe: Optional[Unsubscribe] = None) -> Mail:
    """Aus EINER Angabe alle drei Fassungen – der Verlauf ist der Inhalt der Mail."""
    body = _content_text(lead, extra, firm)
    return Mail(body=body, text=text(subject, body, firm, signer, unsubscribe),
                html=_html(subject, lead, firm, signer, kicker, extra, unsubscribe))


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
    if extra and extra.action:
        a = extra.action
        parts.append("\n".join(x for x in (a.title, a.text, f"{a.label}: {a.url}", a.note) if x))
    return "\n\n".join(p for p in parts if p)


def _signature_lines(firm: Firm, signer: Optional[Signer], body: str) -> list[str]:
    reach = " · ".join(x for x in (firm.phone, firm.email) if x)
    return [*([] if greeted(body) else [GREETING]), *([signer.name] if signer else []),
            firm.name, *([reach] if reach else [])]


def text(subject: str, body: str, firm: Firm, signer: Optional[Signer],
         unsubscribe: Optional[Unsubscribe] = None) -> str:
    foot = " · ".join([firm.name, *firm.address])
    off = [f"{unsubscribe.text} {unsubscribe.label}: {unsubscribe.url}"] if unsubscribe else []
    return "\n".join([dc.title(subject), "", body, "", *_signature_lines(firm, signer, body),
                      "", "—", foot, *off]).strip() + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

#: Abstand zwischen den Blöcken und Rand der Karte – wie im Artefakt.
GAP, PAD = 22, 40


def _p(content: str, size: int = 16, color: str = INK, extra: str = "", cls: str = "ix-ink") -> str:
    return (f'<p class="{cls}" style="margin:0 0 {GAP}px;font-family:{FONT};font-size:{size}px;'
            f'line-height:{size + 8}px;color:{color};{extra}">{content}</p>')


def _rich(par: str) -> str:
    """Ein Absatz: maskiert, Zeilenumbrüche bleiben, Adressen werden Links."""
    out = escape(par).replace("\n", "<br>")
    return re.sub(r"(https?://[^\s<]+)",
                  lambda m: f'<a class="ix-ink" href="{m.group(1)}" style="color:{INK}">'
                            f'{m.group(1)}</a>', out)


def _label(t: str) -> str:
    return (f'<p class="ix-t3" style="margin:0 0 10px;font-family:{FONT};font-size:12px;'
            f'line-height:16px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{TEXT_3}">{escape(t)}</p>') if t else ""


def _box(inner: str) -> str:
    """Gruppiert wird mit einer Haarlinie – nie mit einer Fläche."""
    return (f'<table role="presentation" class="ix-line" width="100%" cellpadding="0" '
            f'cellspacing="0" style="border:1px solid {LINE};border-radius:12px;'
            f'border-collapse:separate;margin:0 0 {GAP}px">{inner}</table>')


def _facts(f: Facts) -> str:
    cell = f"font-family:{FONT};padding:13px 20px;border-bottom:1px solid {LINE};"
    rows = "".join(
        f'<tr><td class="ix-t3 ix-line" style="{cell}font-size:13px;color:{TEXT_3}">'
        f'{escape(k)}</td><td class="ix-ink ix-line" align="right" style="{cell}'
        f'font-size:14px;color:{INK}">{escape(v)}</td></tr>' for k, v in f.rows)
    msg = (f'<tr><td class="ix-t2" colspan="2" style="font-family:{FONT};padding:14px 20px;'
           f'font-size:14px;line-height:21px;color:{TEXT_2}">{_rich(f.message.strip())}</td>'
           f'</tr>' if f.message.strip() else "")
    return _label(f.title) + _box(rows + msg)


def _steps(s: Steps) -> str:
    dot = ("width:10px;height:10px;border-radius:10px;box-sizing:border-box;font-size:0;"
           "line-height:0")
    rows = []
    for i, (label, done) in enumerate(s.items):
        mark = (f'class="ix-ok" style="{dot};background:{GREEN}"' if done else
                f'class="ix-ring" style="{dot};border:2px solid {INK}"')
        if i:
            rows.append(f'<tr><td style="padding:0 0 0 4px"><div class="ix-fill" style="width:2px;'
                        f'height:12px;background:{LINE};font-size:0;line-height:0"></div></td>'
                        f'<td></td></tr>')
        rows.append(f'<tr><td width="22" valign="middle"><div {mark}></div></td>'
                    f'<td class="ix-ink" style="font-family:{FONT};font-size:14px;line-height:22px;'
                    f'color:{INK}">{escape(label)}</td></tr>')
    return (_label(s.title) + '<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 {GAP}px">{"".join(rows)}</table>')


def _call(text: str, firm: Firm) -> str:
    if not (text and firm.phone):
        return ""
    link = (f'<a class="ix-ink" href="tel:{escape(firm.tel or firm.phone)}" style="color:{INK};'
            f'font-weight:600;text-decoration:none;white-space:nowrap">{escape(firm.phone)}</a>')
    return _box(f'<tr><td class="ix-ink" style="padding:16px 20px;font-family:{FONT};'
                f'font-size:14px;line-height:20px;color:{INK}">{escape(text)} {link}</td></tr>')


def _action(a: Optional[Action]) -> str:
    """Ein Knopf in der Farbe der Schrift – der eine laute Punkt der Mail."""
    if a is None:
        return ""
    text = _p(escape(a.text), size=14, extra="margin:0 0 16px") if a.text else ""
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
              f'<td class="ix-btn" style="border-radius:8px;background:{INK}">'
              f'<a class="ix-btn" href="{escape(a.url)}" style="display:inline-block;'
              f'padding:12px 22px;font-family:{FONT};font-size:15px;font-weight:600;'
              f'line-height:20px;color:#FFFFFF;text-decoration:none;border-radius:8px">'
              f'{escape(a.label)}</a></td></tr></table>')
    small = (f'margin:12px 0 0;font-family:{FONT};font-size:12px;line-height:18px;'
             f'color:{TEXT_3};word-break:break-all')
    # Die Adresse steht auch sichtbar da – für ein Mailprogramm ohne Knöpfe, und damit die
    # Mail dieselben Wörter trägt wie ihr Verlauf.
    link = (f'<p class="ix-t3" style="{small}"><a class="ix-t3" href="{escape(a.url)}" '
            f'style="color:{TEXT_3}">{escape(a.url)}</a></p>')
    note = (f'<p class="ix-t3" style="{small};word-break:normal;font-size:13px">'
            f'{escape(a.note)}</p>' if a.note else "")
    return _label(a.title) + _box(f'<tr><td style="padding:18px 20px">{text}{button}{link}'
                                  f'{note}</td></tr>')


def _extra(x: Optional[Extra], firm: Firm) -> str:
    if x is None:
        return ""
    return ((_facts(x.facts) if x.facts else "") + (_steps(x.steps) if x.steps else "")
            + _call(x.call, firm) + _action(x.action))


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
    return (f'<table role="presentation" cellpadding="0" cellspacing="0"><tr><td class="ix-btn" '
            f'width="48" height="48" align="center" valign="middle" style="width:48px;height:48px;'
            f'border-radius:24px;background:{INK};color:#FFFFFF;font-family:{FONT};'
            f'font-size:16px;font-weight:600">{escape(_initials(signer.name))}</td></tr></table>')


def _signature(firm: Firm, signer: Optional[Signer], body: str) -> str:
    link = f'class="ix-t2" style="color:{TEXT_2};text-decoration:none"'
    reach = " · ".join(x for x in (
        f'<a {link} href="tel:{escape(firm.tel or firm.phone)}">{escape(firm.phone)}</a>'
        if firm.phone else "",
        f'<a {link} href="mailto:{escape(firm.email)}">{escape(firm.email)}</a>'
        if firm.email else "") if x)
    head = escape(signer.name) if signer else escape(firm.name)
    lines = [f'<span class="ix-ink" style="font-size:15px;line-height:20px;font-weight:600;'
             f'color:{INK}">{head}</span>', *([escape(firm.name)] if signer else []),
             *([f'<span style="white-space:nowrap">{reach}</span>'] if reach else [])]
    avatar = _avatar(firm, signer)
    pic = (f'<td width="48" valign="middle" style="width:48px;padding:0 16px 0 0">{avatar}</td>'
           if avatar else "")
    greeting = "" if greeted(body) else _p(GREETING, extra="margin:0 0 16px")
    return (greeting + f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>{pic}'
            f'<td class="ix-t2" valign="middle" style="font-family:{FONT};font-size:13px;'
            f'line-height:18px;color:{TEXT_2}">{"<br>".join(lines)}</td></tr></table>')


def _footer(firm: Firm, unsubscribe: Optional[Unsubscribe] = None) -> str:
    """Zwei leise Zeilen, mittig – wer wir sind, wie man uns erreicht; beim Newsletter
    darunter der Abmeldelink."""
    base = get_settings().frontend_base_url.rstrip("/")
    host = urlparse(base).netloc or base
    first = " · ".join([f'<b class="ix-t2" style="font-weight:600;color:{TEXT_2}">'
                        f'{escape(firm.name)}</b>', *(escape(a) for a in firm.address[:2])])
    second = " · ".join([*([escape(firm.phone)] if firm.phone else []),
                         f'<a class="ix-t3" href="{base}" style="color:{TEXT_3};'
                         f'text-decoration:none">{escape(host)}</a>'])
    off = (f'<br><br>{escape(unsubscribe.text)} <a class="ix-t3" href="{escape(unsubscribe.url)}"'
           f' style="color:{TEXT_3};text-decoration:underline">{escape(unsubscribe.label)}</a>'
           if unsubscribe else "")
    return (f'<tr><td class="ix-t3 ix-line ix-pad" align="center" style="padding:20px {PAD}px '
            f'28px;border-top:1px solid {LINE};font-family:{FONT};font-size:12px;'
            f'line-height:18px;color:{TEXT_3};text-align:center">{first}<br>{second}{off}'
            f'</td></tr>')


#: Der dunkle Modus – dort, wo der Client ihn meldet (Apple Mail, Outlook, iOS). Gmail
#: liest ihn nicht und kehrt die Farben selbst um; darum hängt nichts an einer Fläche.
_DARK_BG, _DARK_LINE = "#1F1F1F", "#3A3936"
_DARK = ('<style>:root{color-scheme:light dark;supported-color-schemes:light dark}'
         '@media (max-width:620px){.ix-pad{padding-left:20px!important;'
         'padding-right:20px!important}.ix-h1{font-size:24px!important;line-height:30px!important}}'
         '@media (prefers-color-scheme:dark){'
         f'body,.ix-bg{{background:{_DARK_BG}!important}}'
         '.ix-ink{color:#EDEBE7!important}.ix-t2{color:#C4C0BA!important}'
         '.ix-t3{color:#9C978F!important}.ix-kick{color:#F0453F!important}'
         f'.ix-line{{border-color:{_DARK_LINE}!important}}.ix-fill{{background:{_DARK_LINE}!important}}'
         '.ix-ok{background:#46B176!important}.ix-ring{border-color:#EDEBE7!important}'
         '.ix-btn{background:#EDEBE7!important;color:#111111!important}'
         '.ix-logo-l{display:none!important}.ix-logo-d{display:block!important}}</style>')


def _logo(base: str) -> str:
    img = (f'width="{LOGO_W}" height="{LOGO_H}" alt="{BRAND}" style="display:block;'
           f'border:0;width:{LOGO_W}px;height:{LOGO_H}px')
    return (f'<img class="ix-logo-l" src="{base}{LOGO}" {img}">'
            f'<img class="ix-logo-d" src="{base}{LOGO_DARK}" {img};display:none">')


def _html(subject: str, lead: str, firm: Firm, signer: Optional[Signer], kicker: str,
          extra: Optional[Extra], unsubscribe: Optional[Unsubscribe] = None) -> str:
    """Eine Spalte, 600 px, mittig, umrandet von einer Haarlinie – wie im Artefakt."""
    base = get_settings().frontend_base_url.rstrip("/")
    pars = _paragraphs(lead)
    pre = escape((pars[0] if pars else "")[:140])
    kick = (f'<td class="ix-kick" align="right" valign="top" style="font-family:{FONT};'
            f'font-size:12px;line-height:16px;font-weight:600;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:{RED_TEXT}">{escape(kicker)}</td>'
            ) if kicker else "<td></td>"
    content = "".join(_p(_rich(p)) for p in pars) + _extra(extra, firm)
    head = (f'<tr><td class="ix-pad" style="padding:32px {PAD}px 0"><table role="presentation" '
            f'width="100%" cellpadding="0" cellspacing="0"><tr><td valign="top">{_logo(base)}'
            f'</td>{kick}</tr></table></td></tr>')
    body = (f'<tr><td class="ix-pad" style="padding:28px {PAD}px {PAD - GAP}px">'
            f'<h1 class="ix-ink ix-h1" style="margin:0 0 {GAP}px;font-family:\'Inter Tight\','
            f'{FONT};font-size:28px;line-height:34px;font-weight:700;letter-spacing:-0.03em;'
            f'color:{INK}">{escape(dc.title(subject))}</h1><!--inhalt-->{content}<!--/inhalt-->'
            f'{_signature(firm, signer, lead)}<div style="height:{GAP}px;line-height:'
            f'{GAP}px;font-size:0">&nbsp;</div></td></tr>')
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<title>{escape(dc.title(subject))}</title>{_DARK}</head>'
        '<body class="ix-bg" style="margin:0;padding:0;background:#FFFFFF">'
        f'<span style="display:none;max-height:0;overflow:hidden;opacity:0">{pre}</span>'
        '<table role="presentation" class="ix-bg" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#FFFFFF"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" class="ix-bg ix-line" width="100%" cellpadding="0" '
        f'cellspacing="0" style="max-width:600px;background:#FFFFFF;border:1px solid {LINE};'
        'border-radius:12px;border-collapse:separate;overflow:hidden">'
        f'{head}{body}{_footer(firm, unsubscribe)}'
        '</table></td></tr></table></body></html>')
