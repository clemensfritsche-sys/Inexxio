"""►►► **Die EINE Dokumentvorlage** – Offerte, Auftragsbestätigung, Rechnung, Quittung,
Stornierung, Gutschrift, Mahnung, die AGB: immer derselbe Aufbau. ◄◄◄

A4, Ränder 20 mm, rechte Spalte ab 118 mm. Seite 1: der Dokumenttyp gross und blass oben
links, das Logo (32 mm) oben rechts, darunter links die Anschrift (Fensterkuvert), rechts die
Fakten. Positionen, Summe, Konditionen inklusive Lieferadresse, der AGB-Satz. **Der Absender
steht an EINER Stelle**: in der Fusszeile (Name, Sitz, MWST-Nummer, Seitenzahl). Bei einer
Rechnung darunter der Schweizer Zahlteil. Die AGB folgen als letzte Seite – dieselbe Vorlage.

Wie ``mail_layout.compose`` für Mails: die Daten kommen aus dem Beleg (``voucher_docs``),
hier steht nur, wie sie auf Papier aussehen. **Das Ergebnis ist eigenständiges HTML** – es
wird eingefroren (``voucher_documents.html``), im Browser gezeigt und von ihm als PDF
gedruckt (A4-Druckstil, keine PDF-Bibliothek).
"""

import base64
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Optional

from . import agb as agb_svc

_LOGO = base64.b64encode(
    (Path(__file__).resolve().parent.parent / "assets" / "logo.png").read_bytes()).decode()

#: Die Werte der Design-Tokens – das Papier steht für sich (eingefroren, gedruckt) und kann
#: die Stylesheets der Seite nicht erben.
_STYLE = """
:root{--fg-1:#0A0A0B;--fg-2:#44464A;--fg-3:#5E6064;--fg-4:#A3A5AA;--line:#E3E4E7;
--soft:#E3E4E7;--ok:#1E7F46;--bad:#C8140F;
--display:'Inter Tight','Inter','Helvetica Neue',Arial,sans-serif;
--body:'Inter','Helvetica Neue',Arial,sans-serif;color-scheme:light}
@page{size:A4;margin:0}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:transparent}
body{font-family:var(--body);color:var(--fg-1);font-size:13px;line-height:1.45;
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheets{display:flex;flex-direction:column;align-items:center;gap:32px}
.sheet{position:relative;width:210mm;max-width:100%;min-height:297mm;background:#fff;
padding:16mm 20mm 12mm;display:flex;flex-direction:column;overflow:hidden;
box-shadow:0 1px 2px rgba(10,10,11,.06),0 12px 40px rgba(10,10,11,.10);border-radius:4px}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px}
.word{font:600 var(--size,64px)/1.05 var(--display);letter-spacing:-.045em;color:var(--soft);
white-space:nowrap;padding-bottom:4px}
.logo{width:32mm;height:auto;flex:0 0 auto}
.head{margin-top:16mm;display:grid;grid-template-columns:98mm 1fr}
.to{padding-right:8mm;font-size:13.5px;line-height:1.55}
.facts{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;align-content:start}
.lbl{font:600 10px var(--body);text-transform:uppercase;letter-spacing:.1em;color:var(--fg-4)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.fact{font-size:12.5px}
table.pos{width:100%;border-collapse:collapse;margin-top:14mm}
table.pos th{padding:0 0 10px;font-weight:600;text-align:left}
table.pos th.r,table.pos td.r{text-align:right}
table.pos td{padding:11px 0;border-top:1px solid var(--line);vertical-align:top}
table.pos th:not(:last-child),table.pos td:not(:last-child){padding-right:12px}
.sub{font-size:11.5px;color:var(--fg-3);margin-top:2px}
.part{color:var(--fg-1)}
.sum{margin:4px 0 0 auto;width:320px;display:grid;grid-template-columns:1fr auto;gap:6px 16px;
padding-top:12px;border-top:1px solid var(--line)}
.sum .k{color:var(--fg-3)}.sum .v{text-align:right}
.sum .tot{font:700 15px var(--body);padding-top:10px;border-top:1.5px solid var(--fg-1)}
.note{grid-column:1/-1;font-size:11px;color:var(--fg-3)}
.terms{margin-top:12mm;display:grid;gap:16px}
.terms .v{margin-top:4px;font-size:12.5px}
.agbline{margin:14px 0 0;font-size:11.5px;color:var(--fg-3)}
.after{margin-top:22px;font-size:13px}
.pays{margin-top:22px;display:grid;grid-template-columns:110px 1fr auto;gap:6px 14px;
font-size:12.5px}
.foot{margin-top:auto;padding-top:10mm}
.foot div{display:flex;justify-content:space-between;gap:16px;padding-top:10px;
border-top:1px solid var(--line);font-size:9.5px;color:var(--fg-3)}
.slip{margin:6mm -20mm -12mm;border-top:1px dashed var(--fg-4);display:grid;
grid-template-columns:62mm 1fr;min-height:105mm;font-size:10.5px}
.slip .rcpt{padding:20px 18px;border-right:1px dashed var(--fg-4)}
.slip .pay{padding:20px 18px;display:grid;grid-template-columns:52mm 1fr;gap:16px}
.slip b{display:block;font-weight:600;margin-top:10px}
.slip .h{font:700 12px var(--body)}
.slip .qr svg{width:46mm;height:46mm;display:block;margin-top:14px}
.agb h3{font:600 13px var(--body);margin:16px 0 0}
.agb p,.agb li{margin:4px 0 0;font-size:12px;line-height:1.55;color:var(--fg-2)}
.agb ul{margin:4px 0 0;padding-left:18px}
.agb .intro{margin-top:6mm;font-size:12.5px;color:var(--fg-2)}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
@media print{.sheets{gap:0}.sheet{box-shadow:none;border-radius:0;break-after:page}}
@media screen and (max-width:820px){.sheet{min-height:0;padding:9mm 6mm 6mm}
.head{grid-template-columns:1fr;gap:16px}.slip{display:none}
.top{flex-direction:column-reverse;align-items:flex-start;gap:6mm}.logo{width:24mm}
.word{font-size:min(var(--size,64px),calc(150vw / var(--chars,12)))}
.terms{grid-template-columns:1fr 1fr!important}.sum{width:100%}}
"""

_FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:'
          'wght@400;500;600;700&family=Inter+Tight:wght@600;700&display=swap">')


@dataclass
class Line:
    """Eine Position, wie sie auf dem Papier steht."""
    qty: str
    name: str
    sub: str = ""
    price: str = ""
    amount: str = ""


@dataclass
class Payslip:
    """Der Schweizer Zahlteil (QR-Rechnung) – fertig gelesen aus ``qrbill``."""
    iban: str
    creditor: list[str]
    debtor: list[str]
    reference: str
    currency: str
    amount: str
    info: str
    qr_svg: str


@dataclass
class Doc:
    """**Ein Dokument** – alles, was auf seinem Papier steht, schon als Text."""
    word: str
    number: str
    to: list[str]
    facts: list[tuple[str, str]]
    lines: list[Line] = field(default_factory=list)
    currency: str = "CHF"
    #: Netto, je Satz eine Zeile, dazu Pflichtsätze (Export, Reverse Charge).
    sums: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    total: str = ""
    total_label: str = "Total"
    terms: list[tuple[str, str]] = field(default_factory=list)
    #: Was nach den Konditionen steht – Annahme, Zahlungen, Storno, Mahntext (HTML).
    after: str = ""
    payslip: Optional[Payslip] = None
    #: Absender in der Fusszeile – eine Zeile.
    sender: str = ""
    #: Die AGB, die angehängt werden – ``None`` heisst «keine».
    terms_of: Optional[agb_svc.Terms] = None
    business: bool = True
    #: Statt der Positionen nur ein Text (Mahnung, Stornierung ohne Rechnung).
    letter: str = ""


def render(doc: Doc) -> str:
    """►►► **Das Dokument als eigenständiges HTML** – Seite 1 und die AGB-Seite. ◄◄◄"""
    agb = doc.terms_of
    pages = 2 if agb is not None else 1
    first = _first_page(doc, pages)
    rest = agb_page(agb, business=doc.business, sender=doc.sender, page=2, of=pages) \
        if agb is not None else ""
    title = escape(f"{doc.word} {doc.number}".strip())
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title>{_FONTS}<style>{_STYLE}</style></head>'
            f'<body><div class="sheets">{first}{rest}</div></body></html>')


def standalone_agb(agb: agb_svc.Terms, *, sender: str) -> str:
    """Die AGB allein – die Seite ``/agb`` der Website: beide Teile, dieselbe Vorlage."""
    sheets = "".join(agb_page(agb, part=p, sender=sender, page=i + 1, of=len(agb.parts))
                     for i, p in enumerate(agb.parts))
    return (f'<!doctype html><html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(agb.title)}</title>{_FONTS}<style>{_STYLE}</style></head>'
            f'<body><div class="sheets">{sheets}</div></body></html>')


def _top(word: str) -> str:
    # **Ein langes Wort wird kleiner, nicht abgeschnitten** – «Zahlungserinnerung» muss neben
    # dem Logo Platz haben.
    size = 64 if len(word) <= 12 else (48 if len(word) <= 16 else 40)
    # Schmal steht das Wort unter dem Logo und schrumpft mit der Breite (``--chars``).
    return (f'<div class="top"><div class="word" aria-hidden="true" '
            f'style="--size:{size}px;--chars:{max(len(word), 1)}">{escape(word)}</div>'
            f'<img class="logo" alt="INEXXIO" src="data:image/png;base64,{_LOGO}"></div>')


def _foot(sender: str, page: int, of: int) -> str:
    return (f'<div class="foot"><div><span>{escape(sender)}</span>'
            f'<span>Seite {page}/{of}</span></div></div>')


def _first_page(doc: Doc, pages: int) -> str:
    facts = "".join(f'<span class="lbl">{escape(a)}</span><span class="fact num">{b}</span>'
                    for a, b in doc.facts)
    to = "<br>".join(escape(x) for x in doc.to if x)
    body = _letter(doc) if doc.letter else _positions(doc)
    terms = ""
    if doc.terms:
        cells = "".join(f'<div><div class="lbl">{escape(a)}</div><div class="v">{escape(b)}'
                        f'</div></div>' for a, b in doc.terms)
        terms = (f'<div class="terms" style="grid-template-columns:repeat({len(doc.terms)},'
                 f'1fr)">{cells}</div>')
    agbline = (f'<p class="agbline">Es gelten unsere Allgemeinen Geschäftsbedingungen vom '
               f'{doc.terms_of.day}.</p>' if doc.terms_of is not None else "")
    return (f'<section class="sheet">{_top(doc.word)}'
            f'<div class="head"><div class="to">{to}</div><div class="facts">{facts}</div>'
            f'</div>{body}{terms}{agbline}{doc.after}{_foot(doc.sender, 1, pages)}'
            f'{_slip(doc.payslip) if doc.payslip else ""}</section>')


def _letter(doc: Doc) -> str:
    return f'<div class="after" style="margin-top:14mm">{doc.letter}</div>' + (
        _sums(doc) if doc.total else "")


def _positions(doc: Doc) -> str:
    th = (f'<th class="lbl">Pos.</th><th class="lbl">Menge</th><th class="lbl">Bezeichnung'
          f'</th><th class="lbl r">Preis {escape(doc.currency)}</th>'
          f'<th class="lbl r">Betrag {escape(doc.currency)}</th>')
    rows = "".join(
        f'<tr><td class="num" style="color:var(--fg-3)">{i + 1}</td>'
        f'<td class="num">{escape(ln.qty)}</td>'
        f'<td class="t"><div style="font-weight:500">{escape(ln.name)}</div>'
        + (f'<div class="sub">{ln.sub}</div>' if ln.sub else "")
        + f'</td><td class="r num">{escape(ln.price)}</td>'
        f'<td class="r num">{escape(ln.amount)}</td></tr>'
        for i, ln in enumerate(doc.lines))
    return (f'<table class="pos"><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table>'
            + _sums(doc))


def _sums(doc: Doc) -> str:
    rows = "".join(f'<span class="k">{escape(a)}</span><span class="v num">{escape(b)}</span>'
                   for a, b in doc.sums)
    notes = "".join(f'<span class="note">{escape(n)}</span>' for n in doc.notes)
    return (f'<div class="sum num">{rows}<span class="tot">{escape(doc.total_label)} '
            f'{escape(doc.currency)}</span><span class="tot v">{escape(doc.total)}</span>'
            f'{notes}</div>')


def _slip(p: Payslip) -> str:
    """Der Zahlteil – Empfangsschein und Zahlteil mit dem Swiss QR Code."""
    cred = "<br>".join(escape(x) for x in [p.iban, *p.creditor] if x)
    debt = "<br>".join(escape(x) for x in p.debtor if x)
    money = (f'<div style="margin-top:14px;display:flex;gap:18px"><div><b>Währung</b>'
             f'{escape(p.currency)}</div><div><b>Betrag</b>{escape(p.amount)}</div></div>')
    return (f'<div class="slip"><div class="rcpt"><div class="h">Empfangsschein</div>'
            f'<b>Konto / Zahlbar an</b><div>{cred}</div><b>Referenz</b>'
            f'<div>{escape(p.reference)}</div><b>Zahlbar durch</b><div>{debt}</div>{money}</div>'
            f'<div class="pay"><div><div class="h">Zahlteil</div><div class="qr">{p.qr_svg}'
            f'</div>{money}</div><div style="margin-top:16px"><b>Konto / Zahlbar an</b>'
            f'<div>{cred}</div><b>Referenz</b><div>{escape(p.reference)}</div>'
            f'<b>Zusätzliche Informationen</b><div>{escape(p.info)}</div>'
            f'<b>Zahlbar durch</b><div>{debt}</div></div></div></div>')


def agb_page(agb: agb_svc.Terms, *, business: bool = True,
             part: Optional[agb_svc.Part] = None, sender: str = "",
             page: int = 1, of: int = 1) -> str:
    """►►► **Die AGB als Seite derselben Vorlage** – das Wort «AGB», das Datum, die
    Paragrafen. Für einen Empfänger der Teil, der für ihn gilt (geschäftlich ↔ privat). ◄◄◄"""
    use = part or agb.part_for(business)
    if use is None:
        return ""
    paras = ""
    for para in use.paragraphs:
        items = "".join(f"<li>{escape(t)}</li>" for kind, t in para.blocks if kind == "li")
        texts = "".join(f"<p>{escape(t)}</p>" for kind, t in para.blocks if kind == "p")
        paras += f"<h3>{escape(para.title)}</h3>{texts}" + (f"<ul>{items}</ul>" if items else "")
    facts = (f'<span class="lbl">Gültig ab</span><span class="fact num">{agb.day}</span>'
             f'<span class="lbl">Für</span><span class="fact">'
             f'{escape(use.title.replace("Für ", ""))}</span>')
    intro = f'<p class="intro">{escape(use.intro)}</p>' if use.intro else ""
    return (f'<section class="sheet agb">{_top("AGB")}<div class="facts" '
            f'style="margin-top:12mm;width:fit-content">{facts}</div>{intro}'
            f'<div style="margin-top:4mm">{paras}</div>{_foot(sender, page, of)}</section>')
