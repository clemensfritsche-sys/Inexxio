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
* **Unterschrieben wird mit dem Menschen, im Namen des Unternehmens** – EIN Unterzeichner
  (``as_signer``) für jede Mail, mit Bild daneben (sein Profilbild, sonst seine
  Initialen); eine automatische Mail unterschreibt das Unternehmen, mit dem Bild seines
  Postfachs. Telefon
  und E-Mail sind die der Gesellschaft – keine Funktion, keine Direktnummer, nie «Ihr Team».
* **Wie ein Brief** (Inhaber 28.11.2026, Artefakt «Mail-Layout INEXXIO»): der Gruss («Beste
  Grüsse aus <Ort>») gehört zum Text – gleiche Schrift, gleiche Farbe –, erst danach trennt eine
  Haarlinie die **Unterschrift** ab: das Bild rund (``services/portrait``: Profilbild, sonst
  Initialen), daneben Name, die E-Mail des Postfachs und die Telefonnummer, je eine Zeile.
* **Kopf = Briefkopf**: INEXXIO mit «Kranbau · Fahrzeugbau · Service» links, «ehemals HS
  Steiner» rechts, darunter eine Haarlinie; dann die Überschrift (= Betreff) in eigener Zeile.
* **Fusszeile unter der Karte**: Gesellschaft, Anschrift, E-Mail, Website – leise, grau.
* **Unten ein Streifen** (``letter.promo`` in ``website/src/config/inquiry.mjs``, in jeder
  Sprache): Bild, Stichwort, Titel, Satz, Link – eine kleine Werbefläche in jeder Mail.
* **Der Absendername folgt daraus**: «Clemens Fritsche · INEXXIO» bzw. «INEXXIO».
* **Links öffnen ein neues Fenster** (``target="_blank"``).
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
from urllib.parse import quote, urlparse

from ..core.config import get_settings
from ..domain import communication as dc
from . import portrait

BRAND = "INEXXIO"
#: Der Briefkopf: links die Wortmarke mit Unterzeile «Kranbau · Fahrzeugbau · Service»
#: (``inexxio-horizontal-tagline-*``, Design System, Logo v5 «F1»), rechts «ehemals HS Steiner»
#: (unterste Zeile von ``inexxio-stacked-tagline-*``, so gross, dass es mittig zur Wortmarke
#: lesbar steht). Je als PNG in doppelter Auflösung, hell und dunkel. ``logo.png`` bleibt im
#: Ordner liegen: frühere Mails zeigen es.
LOGO, LOGO_DARK = "/mail/kopf.png", "/mail/kopf-dark.png"
LOGO_W, LOGO_H = 176, 64
LOGO_ALT = "INEXXIO – Kranbau · Fahrzeugbau · Service"
FORMER, FORMER_DARK = "/mail/ehemals.png", "/mail/ehemals-dark.png"
FORMER_W, FORMER_H = 157, 12
FORMER_ALT = "ehemals HS Steiner"
FONT = "Inter, Arial, Helvetica, sans-serif"
DISPLAY = f"'Inter Tight',{FONT}"
#: Farben aus dem Design System (``colors_and_type.css``): Ink = Grau-950, Text = Grau-700,
#: leise = Grau-600, Haarlinie = Grau-200.
INK, TEXT_2, TEXT_3, LINE = "#0A0A0B", "#44464A", "#5E6064", "#E3E4E7"


@dataclass
class Firm:
    """Wer schreibt – die eigene Gesellschaft hinter dem Postfach."""
    name: str
    address: list[str] = field(default_factory=list)
    phone: str = ""             # zur Anzeige («+41 79 505 83 02»)
    tel: str = ""               # zum Wählen («+41795058302»)
    email: str = ""
    picture: str = ""           # das Bild des Postfachs (Google-Konto)
    city: str = ""              # der Ort im Gruss («Beste Grüsse aus Tuttwil»)


@dataclass
class Signer:
    """Der Mensch, der geschrieben hat."""
    name: str
    photo: str = ""


def as_signer(person: Any) -> Signer:
    """►►► **Der Unterzeichner – EINE Stelle** für jede Mail (Postfach, Beleg, Dokument):
    Name und Profilbild der Person. Wer überhaupt unterschreibt (Mensch oder Unternehmen),
    entscheidet der Absender; wie er unterschreibt, steht nur hier."""
    return Signer(name=getattr(person, "display_name", None) or "",
                  photo=getattr(person, "photo_url", None) or "")


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
    #: Satz vor der Telefonnummer der Gesellschaft («Eilt es? Dann rufen Sie uns an:»).
    call: str = ""
    action: Optional[Action] = None
    #: ►►► **Ein Beleg-Dokument** (Offerte, Rechnung …): der Fortschritt quer, die
    #: Positionen und EIN grosser Knopf zum Online-Beleg (``Paper``).
    paper: Optional["Paper"] = None


@dataclass
class Paper:
    """Was eine Beleg-Mail zeigt – die Stationen, die Positionen, der eine Knopf."""
    stations: list[str]
    #: Welche Station gerade ist (0 …); ``None`` = ohne Fortschritt (Mahnung).
    at: Optional[int]
    rows: list[tuple[str, str, str]]          # (Menge, Bezeichnung, Betrag)
    total_label: str
    total: str
    label: str
    url: str
    tax: Optional[tuple[str, str]] = None


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
                email=mailbox_address or company.email or "", picture=picture or "",
                city=(company.city or "").strip())


def letter(lang: str = "de") -> dict:
    """Die Wörter des Briefs in einer Sprache: Gruss und Streifen (``website/src/config/inquiry.mjs``)."""
    from .inquiry import words
    return words(lang)["letter"]


def closing(firm: Firm, lang: str = "de") -> str:
    """Der Gruss vor der Unterschrift – mit dem Ort der Gesellschaft, sonst ohne."""
    w = letter(lang)
    return w["greeting"].replace("{city}", firm.city) if firm.city else w["greetingPlain"]


def sender_name(signer: Optional[Signer]) -> str:
    """Der Name im «Von» – der Mensch und die Marke, oder nur die Marke."""
    return f"{signer.name} · {BRAND}" if signer else BRAND


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body or "") if p.strip()]


def greeted(body: str) -> bool:
    """Steht am Schluss schon ein Gruss? Dann setzt die Vorlage keinen zweiten."""
    lines = [ln.strip() for ln in (body or "").split("\n") if ln.strip()]
    return any(dc.is_greeting(ln) for ln in lines[-3:])


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
            extra: Optional[Extra] = None, unsubscribe: Optional[Unsubscribe] = None,
            lang: str = "de") -> Mail:
    """Aus EINER Angabe alle drei Fassungen – der Verlauf ist der Inhalt der Mail."""
    body = _content_text(lead, extra, firm)
    return Mail(body=body, text=text(subject, body, firm, signer, unsubscribe, lang),
                html=_html(subject, lead, firm, signer, extra, unsubscribe, lang))


def _content_text(lead: str, extra: Optional[Extra], firm: Firm) -> str:
    parts = ["\n\n".join(_paragraphs(lead))]
    if extra and extra.call and firm.phone:
        parts.append(f"{extra.call} {firm.phone}")
    if extra and extra.action:
        a = extra.action
        parts.append("\n".join(x for x in (a.title, a.text, f"{a.label}: {a.url}", a.note) if x))
    if extra and extra.paper:
        pp = extra.paper
        parts.append("\n".join([*(f"{q} × {n}  {v}" for q, n, v in pp.rows),
                                f"{pp.total_label}: {pp.total}", f"{pp.label}: {pp.url}"]))
    return "\n\n".join(p for p in parts if p)


def _signature_lines(firm: Firm, signer: Optional[Signer], body: str,
                     lang: str = "de") -> list[str]:
    """Gruss, dann wer unterschreibt: Name, E-Mail des Postfachs, Telefon."""
    return [*([] if greeted(body) else [closing(firm, lang), ""]),
            signer.name if signer else firm.name, *(x for x in (firm.email, firm.phone) if x)]


def _footer_parts(firm: Firm) -> list[str]:
    """Die Fusszeile unter der Karte: Gesellschaft, Anschrift, E-Mail, Website."""
    return [x for x in (firm.name, ", ".join(firm.address), firm.email, _host()) if x]


def _host() -> str:
    base = get_settings().frontend_base_url.rstrip("/")
    return urlparse(base).netloc or base


def _promo_text(lang: str) -> list[str]:
    p = letter(lang)["promo"]
    base = get_settings().frontend_base_url.rstrip("/")
    return [f"{p['kicker']}: {p['title']}", p["text"], f"{p['label']}: {base}{p['href']}"]


def text(subject: str, body: str, firm: Firm, signer: Optional[Signer],
         unsubscribe: Optional[Unsubscribe] = None, lang: str = "de") -> str:
    off = [f"{unsubscribe.text} {unsubscribe.label}: {unsubscribe.url}"] if unsubscribe else []
    return "\n".join([dc.title(subject), "", body, "", *_signature_lines(firm, signer, body, lang),
                      "", "—", *_promo_text(lang), "", " · ".join(_footer_parts(firm)),
                      *off]).strip() + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

#: Abstand zwischen den Blöcken und Rand der Karte – wie im Artefakt.
GAP, PAD = 22, 40
#: Radien wie v4: Karte 8 px, Knopf 6 px.
CARD_R, BTN_R = 8, 6
#: Ein Link öffnet ein neues Fenster.
NEW = ' target="_blank" rel="noopener"'


#: Die Schrift des Textes – eine Spur grösser als die übrigen Zeilen, damit die Nachricht das
#: Lauteste der Mail ist.
TEXT_SIZE = 17


def _p(content: str, size: int = TEXT_SIZE, color: str = INK, extra: str = "",
       cls: str = "ix-ink") -> str:
    return (f'<p class="{cls}" style="margin:0 0 {GAP}px;font-family:{FONT};font-size:{size}px;'
            f'line-height:{round(size * 1.6)}px;color:{color};{extra}">{content}</p>')


def _rich(par: str) -> str:
    """Ein Absatz: maskiert, Zeilenumbrüche bleiben, Adressen werden Links."""
    out = escape(par).replace("\n", "<br>")
    return re.sub(r"(https?://[^\s<]+)",
                  lambda m: f'<a class="ix-ink" href="{m.group(1)}"{NEW} style="color:{INK}">'
                            f'{m.group(1)}</a>', out)


def _label(t: str) -> str:
    return (f'<p class="ix-t3" style="margin:0 0 10px;font-family:{FONT};font-size:12px;'
            f'line-height:16px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:{TEXT_3}">{escape(t)}</p>') if t else ""


def _box(inner: str) -> str:
    """Gruppiert wird mit einer Haarlinie – nie mit einer Fläche."""
    return (f'<table role="presentation" class="ix-line" width="100%" cellpadding="0" '
            f'cellspacing="0" style="border:1px solid {LINE};border-radius:{CARD_R}px;'
            f'border-collapse:separate;margin:0 0 {GAP}px">{inner}</table>')


def _call(text: str, firm: Firm) -> str:
    if not (text and firm.phone):
        return ""
    link = (f'<a class="ix-ink" href="tel:{escape(firm.tel or firm.phone)}" style="color:{INK};'
            f'font-weight:600;text-decoration:none;white-space:nowrap">{escape(firm.phone)}</a>')
    return _p(f"{escape(text)} {link}")


def _action(a: Optional[Action]) -> str:
    """Ein Knopf in der Farbe der Schrift – der eine laute Punkt der Mail."""
    if a is None:
        return ""
    text = _p(escape(a.text), size=14, extra="margin:0 0 16px") if a.text else ""
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
              f'<td class="ix-btn" style="border-radius:{BTN_R}px;background:{INK}">'
              f'<a class="ix-btn" href="{escape(a.url)}"{NEW} style="display:inline-block;'
              f'padding:12px 22px;font-family:{FONT};font-size:15px;font-weight:600;'
              f'line-height:20px;color:#FFFFFF;text-decoration:none;border-radius:{BTN_R}px">'
              f'{escape(a.label)}</a></td></tr></table>')
    small = (f'margin:12px 0 0;font-family:{FONT};font-size:12px;line-height:18px;'
             f'color:{TEXT_3};word-break:break-all')
    # Die Adresse steht auch sichtbar da – für ein Mailprogramm ohne Knöpfe, und damit die
    # Mail dieselben Wörter trägt wie ihr Verlauf.
    link = (f'<p class="ix-t3" style="{small}"><a class="ix-t3" href="{escape(a.url)}"{NEW} '
            f'style="color:{TEXT_3}">{escape(a.url)}</a></p>')
    note = (f'<p class="ix-t3" style="{small};word-break:normal;font-size:13px">'
            f'{escape(a.note)}</p>' if a.note else "")
    return _label(a.title) + _box(f'<tr><td style="padding:18px 20px">{text}{button}{link}'
                                  f'{note}</td></tr>')


def _extra(x: Optional[Extra], firm: Firm) -> str:
    if x is None:
        return ""
    return (_call(x.call, firm) + _action(x.action)
            + (_paper(x.paper) if x.paper else ""))


def _paper(pp: Paper) -> str:
    """►►► **Der Beleg in der Mail** – Fortschritt quer, Positionen, EIN Knopf. ◄◄◄ Mit den
    Klassen des dunklen Modus (``ix-ink`` · ``ix-t3`` · ``ix-line`` · ``ix-btn``)."""
    out = ""
    if pp.at is not None:
        n = len(pp.stations)
        cells = ""
        for i in range(n):
            on = i <= pp.at
            cells += (f'<td width="10" style="width:10px"><div class="{"ix-btn" if on else "ix-line"}"'
                      f' style="width:10px;height:10px;border-radius:5px;background:'
                      f'{INK if on else "transparent"};border:1.5px solid '
                      f'{INK if on else "#B5B7BC"};box-sizing:border-box"></div></td>')
            if i < n - 1:
                cells += (f'<td style="padding:0 6px"><div class="{"ix-btn" if i < pp.at else "ix-fill"}"'
                          f' style="height:1px;background:{INK if i < pp.at else LINE}"></div></td>')
        labels = "".join(
            f'<td valign="top" class="{"ix-ink" if i <= pp.at else "ix-t3"}" style="font-family:'
            f'{FONT};font-size:12px;line-height:16px;padding-top:8px;color:'
            f'{INK if i <= pp.at else TEXT_3};font-weight:{600 if i == pp.at else 400};'
            f'text-align:{"left" if i == 0 else ("right" if i == n - 1 else "center")}">'
            f'{escape(s)}</td>' for i, s in enumerate(pp.stations))
        out += (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="margin:8px 0 4px"><tr>{cells}</tr></table><table role="presentation" '
                f'width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px"><tr>'
                f'{labels}</tr></table>')
    cell = (f'font-family:{FONT};font-size:14px;line-height:20px;color:{INK};padding:10px 0;'
            f'border-top:1px solid {LINE}')
    rows = "".join(
        f'<tr><td class="ix-ink ix-line" style="{cell}">{escape(q)} × {escape(nm)}</td>'
        f'<td align="right" class="ix-ink ix-line" style="{cell};white-space:nowrap;'
        f'font-variant-numeric:tabular-nums">{escape(v)}</td></tr>' for q, nm, v in pp.rows)
    if pp.tax:
        rows += (f'<tr><td class="ix-t3 ix-line" style="{cell};color:{TEXT_3}">{escape(pp.tax[0])}'
                 f'</td><td align="right" class="ix-t3 ix-line" style="{cell};color:{TEXT_3};'
                 f'white-space:nowrap">{escape(pp.tax[1])}</td></tr>')
    tot = (f'font-family:{FONT};font-size:15px;font-weight:700;color:{INK};padding:12px 0 0;'
           f'border-top:1.5px solid {INK}')
    rows += (f'<tr><td class="ix-ink ix-ring" style="{tot}">{escape(pp.total_label)}</td>'
             f'<td align="right" class="ix-ink ix-ring" style="{tot};white-space:nowrap">'
             f'{escape(pp.total)}</td></tr>')
    out += (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 28px">{rows}</table>')
    out += (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="margin:0 0 32px"><tr><td class="ix-btn" align="center" style="border-radius:'
            f'{BTN_R}px;background:{INK}"><a class="ix-btn" href="{escape(pp.url)}"{NEW} style="display:'
            f'block;padding:16px 24px;font-family:{FONT};font-size:16px;font-weight:600;'
            f'line-height:20px;color:#FFFFFF;text-decoration:none;border-radius:{BTN_R}px">'
            f'{escape(pp.label)}</a></td></tr></table>')
    return out


def _avatar(firm: Firm, signer: Optional[Signer]) -> str:
    """Das Bild neben der Unterschrift, rund (``portrait``): Profilbild, Postfach-Bild oder die
    Initialen; ohne Mensch und ohne Postfach-Bild keines. Outlook am Computer zeigt es eckig."""
    pic = (signer.photo if signer else firm.picture) or ""
    if not (pic or signer):
        return ""
    src = escape(portrait.url(pic, signer.name if signer else firm.name))
    w = portrait.SIZE
    return (f'<img src="{src}" width="{w}" height="{w}" alt="" style="display:block;'
            f'width:{w}px;height:{w}px;border:0;border-radius:50%">')


def _signature(firm: Firm, signer: Optional[Signer], body: str, lang: str = "de") -> str:
    """►►► **Wie ein Brief** – der Gruss gehört zum Text (gleiche Schrift, gleiche Farbe), dann
    eine Haarlinie, darunter das Bild rund und daneben Name, E-Mail des Postfachs, Telefon. ◄◄◄"""
    link = f'class="ix-t2" style="color:{TEXT_2};text-decoration:none"'
    lines = [f'<div class="ix-ink" style="font-size:16px;line-height:22px;font-weight:600;'
             f'color:{INK}">{escape(signer.name if signer else firm.name)}</div>']
    if firm.email:
        lines.append(f'<div><a {link} href="mailto:{escape(firm.email)}">{escape(firm.email)}</a></div>')
    if firm.phone:
        lines.append(f'<div><a {link} href="tel:{escape(firm.tel or firm.phone)}">'
                     f'{escape(firm.phone)}</a></div>')
    avatar = _avatar(firm, signer)
    pic = (f'<td width="{portrait.SIZE}" valign="middle" style="width:{portrait.SIZE}px;'
           f'padding:0 14px 0 0">{avatar}</td>' if avatar else "")
    who = (f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>{pic}'
           f'<td class="ix-t2" valign="middle" style="font-family:{FONT};font-size:14px;'
           f'line-height:20px;color:{TEXT_2}">{"".join(lines)}</td></tr></table>')
    greeting = "" if greeted(body) else _p(escape(closing(firm, lang)))
    return (greeting + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td class="ix-line" style="border-top:1px solid {LINE};padding:20px 0 0">'
            f'{who}</td></tr></table>')


#: Das Bild des Streifens – so gross, wie es in der Mail steht (doppelt gerechnet).
PROMO_W, PROMO_H = 96, 72


def _promo(lang: str = "de", unsubscribe: Optional[Unsubscribe] = None) -> str:
    """►►► **Der Streifen unten – eine kleine Werbefläche in jeder Mail.** ◄◄◄ Bild, Stichwort,
    Titel, Satz, Link; der ganze Streifen ist der Link. Beim Newsletter darunter der Abmeldelink.
    Die Wörter stehen in ``website/src/config/inquiry.mjs`` (``letter.promo``), in jeder Sprache."""
    p = letter(lang)["promo"]
    base = get_settings().frontend_base_url.rstrip("/")
    small = f"font-family:{FONT};font-size:13px;line-height:19px"
    card = (f'<a href="{escape(base + p["href"])}"{NEW} style="display:block;text-decoration:none;'
            f'color:inherit"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td width="{PROMO_W}" valign="middle" style="width:{PROMO_W}px;padding:0 18px 0 0">'
            f'<img src="{escape(base + p["src"])}" width="{PROMO_W}" height="{PROMO_H}" '
            f'alt="{escape(p["alt"])}" style="display:block;width:{PROMO_W}px;height:{PROMO_H}px;'
            f'border:0;border-radius:{BTN_R}px"></td><td valign="middle">'
            f'<div class="ix-t3" style="font-family:{FONT};font-size:11px;line-height:16px;'
            f'font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:{TEXT_3};'
            f'margin:0 0 3px">{escape(p["kicker"])}</div>'
            f'<div class="ix-ink" style="font-family:{DISPLAY};font-size:16px;line-height:21px;'
            f'font-weight:700;letter-spacing:-0.01em;color:{INK};margin:0 0 3px">'
            f'{escape(p["title"])}</div>'
            f'<div class="ix-t2" style="{small};color:{TEXT_2}">{escape(p["text"])} '
            f'<span class="ix-ink" style="font-weight:600;color:{INK};white-space:nowrap">'
            f'{escape(p["label"])}&nbsp;→</span></div></td></tr></table></a>')
    off = (f'<p class="ix-t3" style="margin:16px 0 0;font-family:{FONT};font-size:12px;'
           f'line-height:18px;color:{TEXT_3}">{escape(unsubscribe.text)} <a class="ix-t3" '
           f'href="{escape(unsubscribe.url)}"{NEW} style="color:{TEXT_3};text-decoration:underline">'
           f'{escape(unsubscribe.label)}</a></p>' if unsubscribe else "")
    return (f'<tr><td class="ix-line ix-pad" style="padding:20px {PAD}px 22px;border-top:1px solid '
            f'{LINE}">{card}{off}</td></tr>')


#: Der dunkle Modus – dort, wo der Client ihn meldet (Apple Mail, Outlook, iOS). Gmail
#: liest ihn nicht und kehrt die Farben selbst um; darum hängt nichts an einer Fläche.
#: Am Handy rutscht «ehemals HS Steiner» unter die Wortmarke (``.ix-col``).
_DARK_BG, _DARK_LINE = "#1F1F1F", "#3A3936"
_DARK = ('<style>:root{color-scheme:light dark;supported-color-schemes:light dark}'
         '@media (max-width:620px){.ix-pad{padding-left:24px!important;'
         'padding-right:24px!important}.ix-h1{font-size:23px!important;line-height:29px!important}'
         '.ix-col{display:block!important;width:100%!important;text-align:left!important}'
         '.ix-former{padding:12px 0 0!important}}'
         '@media (prefers-color-scheme:dark){'
         f'body,.ix-bg{{background:{_DARK_BG}!important}}'
         '.ix-ink{color:#EDEBE7!important}.ix-t2{color:#C4C0BA!important}'
         '.ix-t3{color:#9C978F!important}'
         f'.ix-line{{border-color:{_DARK_LINE}!important}}.ix-fill{{background:{_DARK_LINE}!important}}'
         '.ix-ok{background:#46B176!important}.ix-ring{border-color:#EDEBE7!important}'
         '.ix-btn{background:#EDEBE7!important;color:#111111!important}'
         '.ix-logo-l{display:none!important}.ix-logo-d{display:block!important}}</style>')


def _pair(base: str, light: str, dark: str, w: int, h: int, alt: str) -> str:
    """Ein Bild hell und dunkel – das Mailprogramm zeigt das passende (``_DARK``)."""
    img = (f'width="{w}" height="{h}" alt="{alt}" style="display:block;border:0;'
           f'width:{w}px;height:{h}px')
    return (f'<img class="ix-logo-l" src="{base}{light}" {img}">'
            f'<img class="ix-logo-d" src="{base}{dark}" {img};display:none">')


def _letterhead(base: str) -> str:
    """►► **Der Briefkopf** – INEXXIO mit Unterzeile links, «ehemals HS Steiner» rechts, mittig
    zur Wortmarke; darunter eine Haarlinie. Am Handy steht «ehemals» unter der Wortmarke. ◄◄"""
    brand = _pair(base, LOGO, LOGO_DARK, LOGO_W, LOGO_H, LOGO_ALT)
    former = _pair(base, FORMER, FORMER_DARK, FORMER_W, FORMER_H, FORMER_ALT)
    return (f'<tr><td class="ix-pad ix-line" style="padding:26px {PAD}px 22px;border-bottom:1px '
            f'solid {LINE}"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            f'<tr><td class="ix-col" valign="middle" style="text-align:left">{brand}</td>'
            f'<td class="ix-col ix-former" valign="middle" align="right" style="text-align:right">'
            f'<div style="display:inline-block">{former}</div></td></tr></table></td></tr>')


def _footer(firm: Firm) -> str:
    """Die leise Zeile unter der Karte – Gesellschaft, Anschrift, E-Mail, Website. Selbst
    verlinkt und grau, damit kein Mailprogramm die Anschrift zum blauen Link macht."""
    link = f'class="ix-t3" style="color:{TEXT_3};text-decoration:none"'
    base = get_settings().frontend_base_url.rstrip("/")
    where = ", ".join(firm.address)
    maps = "https://www.google.com/maps/search/?api=1&query=" + quote(f"{firm.name}, {where}")
    parts = [escape(firm.name),
             *([f'<a {link} href="{escape(maps)}"{NEW}>{escape(where)}</a>'] if where else []),
             *([f'<a {link} href="mailto:{escape(firm.email)}">{escape(firm.email)}</a>']
               if firm.email else []),
             f'<a {link} href="{escape(base)}"{NEW}>{escape(_host())}</a>']
    return (f'<tr><td class="ix-pad ix-t3" style="padding:14px {PAD}px 0;font-family:{FONT};'
            f'font-size:12px;line-height:18px;color:{TEXT_3}">{" · ".join(parts)}</td></tr>')


def _html(subject: str, lead: str, firm: Firm, signer: Optional[Signer],
          extra: Optional[Extra], unsubscribe: Optional[Unsubscribe] = None,
          lang: str = "de") -> str:
    """Eine Spalte, 600 px, mittig, umrandet von einer Haarlinie: der Briefkopf, die Überschrift,
    Inhalt und Gruss, eine Haarlinie, die Unterschrift, der Streifen; darunter die Fusszeile."""
    base = get_settings().frontend_base_url.rstrip("/")
    pars = _paragraphs(lead)
    pre = escape((pars[0] if pars else "")[:140])
    content = "".join(_p(_rich(p)) for p in pars) + _extra(extra, firm)
    title = (f'<h1 class="ix-ink ix-h1" style="margin:0 0 24px;font-family:{DISPLAY};'
             f'font-size:28px;line-height:34px;font-weight:700;letter-spacing:-0.025em;'
             f'color:{INK}">{escape(dc.title(subject))}</h1>')
    body = (f'<tr><td class="ix-pad" style="padding:34px {PAD}px 28px">{title}'
            f'<!--inhalt-->{content}<!--/inhalt-->{_signature(firm, signer, lead, lang)}</td></tr>')
    return (
        f'<!doctype html><html lang="{escape(lang)}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<title>{escape(dc.title(subject))}</title>{_DARK}</head>'
        '<body class="ix-bg" style="margin:0;padding:0;background:#FFFFFF">'
        f'<span style="display:none;max-height:0;overflow:hidden;opacity:0">{pre}</span>'
        '<table role="presentation" class="ix-bg" width="100%" cellpadding="0" cellspacing="0" '
        'style="background:#FFFFFF"><tr><td align="center" style="padding:24px 12px 28px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:600px"><tr><td>'
        '<table role="presentation" class="ix-bg ix-line" width="100%" cellpadding="0" '
        f'cellspacing="0" style="background:#FFFFFF;border:1px solid {LINE};'
        f'border-radius:{CARD_R}px;border-collapse:separate;overflow:hidden">'
        f'{_letterhead(base)}{body}{_promo(lang, unsubscribe)}'
        f'</table></td></tr>{_footer(firm)}</table></td></tr></table></body></html>')
