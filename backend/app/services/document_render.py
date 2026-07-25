"""PDF-Rendering eines Dokuments im **Inexxio Design System** (WeasyPrint).

Der Renderer ist die Server-Entsprechung der Web-Ansicht: dieselben Design-Tokens
(Rot ``#E51A14`` als einziger lauter Akzent, warme Neutraltöne, Inter/Inter Tight),
aber als amtliches A4-Dokument mit Briefkopf, Fusszeile und Seitenzahlen.

**Fonts sind gebündelt** (``app/assets/fonts``) und werden per ``@font-face`` eingebettet –
kein Netzwerkzugriff zur Render-Zeit (deterministisch, Cloud-Run-tauglich). Fällt eine
Glyphe aus Inter heraus, greift der DejaVu-Fallback aus dem Container.
"""

import html
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from . import address

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"
_FONT_DIR = _ASSET_DIR / "fonts"
_LOGO_FILE = _ASSET_DIR / "img" / "inexxio-logo.png"

# ─── Inexxio-Tokens (Spiegel von styles/design-system/colors_and_type.css) ────────
_RED = "#E51A14"        # der eine laute Akzent
_INK = "#0A0A0B"        # fg-1 – Titel/Überschriften
_BODY = "#3A3A3D"       # fg-2 – Fliesstext
_MUTED = "#6E6E73"      # fg-3 – Meta/Fusszeile
_HAIRLINE = "#E9E7E1"   # border-1
_SAND = "#F4F3F0"       # bg-2


def _font_face_css() -> str:
    def face(family: str, weight: int, file: str) -> str:
        p = (_FONT_DIR / file).as_uri()
        return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
                f"font-style:normal;src:url('{p}') format('truetype');}}")
    faces = [
        face("Inter", 400, "Inter-400.ttf"),
        face("Inter", 500, "Inter-500.ttf"),
        face("Inter", 600, "Inter-600.ttf"),
        face("Inter", 700, "Inter-700.ttf"),
        face("Inter Tight", 700, "InterTight-700.ttf"),
        face("Inter Tight", 800, "InterTight-800.ttf"),
    ]
    return "".join(faces)


def _esc(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def _css_str(v) -> str:
    """Wert für ein CSS-String-Literal (z. B. ``content:``) neutralisieren.

    ``html.escape`` ist hier der falsche Escaper – in einer CSS-Zeichenkette müssen
    Backslash und Anführungszeichen mit Backslash maskiert und Zeilenumbrüche entfernt
    werden (sonst bricht der Firmenname mit ``"``/``\\`` die Fusszeile)."""
    return (str(v) if v is not None else "").replace("\\", "\\\\").replace('"', '\\"') \
        .replace("\n", " ").replace("\r", " ")


def _markdown_html(body: str, image_resolver=None) -> str:
    """Markdown-Body → HTML fürs PDF (GFM-Tabellen, Listen, fett/kursiv, Bilder, Zitate, Code).

    ``image_resolver`` (optional) bekommt jede Bild-URL und liefert eine WeasyPrint-taugliche
    Quelle zurück (i. d. R. eine ``data:``-URI aus der Attachment-Ablage) – sonst kann
    WeasyPrint auth-geschützte Attachment-URLs nicht laden."""
    import re
    import markdown as _md
    if not (body or "").strip():
        return ""
    out = _md.markdown(
        str(body),
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
        output_format="html",
    )
    if image_resolver is not None:
        def _rw(m):
            src = m.group(1)
            resolved = image_resolver(src) or src
            return f'src="{resolved}"'
        out = re.sub(r'src="([^"]*)"', _rw, out)
    return out


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return _esc(value) if value else ""


def _obj_nr(object_id: Optional[int]) -> str:
    return str(object_id).zfill(9) if object_id else "—"


def _address_lines(company: dict) -> list[str]:
    """Saubere, mehrzeilige Firmen-Anschrift für den Briefkopf (nur befüllte Zeilen)."""
    # Strassen-/Ort-Zusammenbau zentral (services/address) – identisch zu Etikett & Versand.
    addr = address.make(
        street1=address._join(company.get("street"), company.get("street_nr")),
        zip=company.get("zip_code"), city=company.get("city"))
    street = "" if addr["street1"] == address.DASH else addr["street1"]
    place = " ".join(x for x in [addr["zip"], addr["city"]] if x)
    contact = " · ".join(str(x) for x in [company.get("email"), company.get("phone")] if x)
    ids = " · ".join(str(x) for x in [
        f"UID {company.get('uid_number')}" if company.get("uid_number") else None,
        f"MWST {company.get('vat_number')}" if company.get("vat_number") else None,
    ] if x)
    lines = [company.get("company_name") or "Inexxio", street, place,
             company.get("country"), contact, ids]
    return [str(x) for x in lines if x]


def _signoffs_html(signoffs: list[dict] | None) -> str:
    """Freigabe-/Unterschriften-Layer (DocuSign-Prinzip: auf die unveränderliche Basis
    gerendert). Jede Partei: Unterschrift-Bild ODER «Bestätigt»/«ausstehend» + Name + Datum.

    Bilder werden als **data-URI** übergeben (der Aufrufer löst sie aus der Ablage auf) –
    keine Netzwerk-/Auth-Abhängigkeit im PDF-Renderer."""
    if not signoffs:
        return ""
    cells = []
    for s in signoffs:
        status = s.get("status")
        if status == "signed" and s.get("image"):
            mark = f'<img class="sig-img" src="{s["image"]}" alt="">'
        elif status == "signed":
            mark = '<span class="sig-ok">✓ Bestätigt</span>'
        elif status == "rejected":
            mark = '<span class="sig-no">Abgelehnt</span>'
        else:
            mark = '<span class="sig-pending">ausstehend</span>'
        action = "Unterschrift" if s.get("action") == "sign" else "Bestätigung"
        meta = action + (f" · {_fmt_date(s['acted_at'])}" if s.get("acted_at") else "")
        cells.append(
            f'<div class="sig-cell"><div class="sig-line">{mark}</div>'
            f'<div class="sig-name">{_esc(s.get("name") or "")}</div>'
            f'<div class="sig-meta">{_esc(meta)}</div></div>'
        )
    return ('<div class="signoffs"><div class="signoffs-title">Freigaben</div>'
            f'<div class="sig-grid">{"".join(cells)}</div></div>')


def render_pdf(content: dict, *, company: dict | None = None,
               object_id: Optional[int] = None, issued_at=None,
               signoffs: list[dict] | None = None, image_resolver=None) -> bytes:
    """Ein Dokument (kanonischer ``content``) als markengetreues A4-PDF rendern.

    ``object_id`` = Instanz-Objektnummer (die Dokumentennummer), ``issued_at`` =
    Instanz-Freigabedatum. Beides kann beim Entwurf noch fehlen (Vorschau). ``signoffs`` =
    Freigabe-Parteien (mit Unterschrift-Bild als data-URI). ``image_resolver`` löst Bild-URLs
    im Markdown-Body zu WeasyPrint-tauglichen Quellen (data-URI) auf."""
    from weasyprint import HTML

    company = company or {}
    address_html = "<br>".join(_esc(ln) for ln in _address_lines(company))
    logo_html = (f'<img class="logo" src="{_LOGO_FILE.as_uri()}" alt="">'
                 if _LOGO_FILE.exists()
                 else f'<div class="brand">{_esc(company.get("company_name") or "Inexxio")}'
                      f'<span class="dot">.</span></div>')

    title = content.get("title") or "Dokument"
    subtitle = content.get("subtitle")

    # Meta: Nummer = Instanz-Objektnummer, Datum = Instanz-Freigabe. Keine Version, kein «gültig ab».
    meta_bits = [f"Nr. {_obj_nr(object_id)}" if object_id else "Entwurf"]
    if issued_at:
        meta_bits.append(f"Datum {_fmt_date(issued_at)}")

    body_html = _markdown_html(content.get("body") or "", image_resolver)

    # Fusszeile lebt in einem CSS-``content``-String → CSS-escapen (nicht HTML).
    company_name = company.get("company_name") or "Inexxio"
    footer_left = f"{_css_str(company_name)} · Dok. {_obj_nr(object_id)}"

    doc = f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><style>
{_font_face_css()}
@page {{
  size: A4;
  margin: 22mm 20mm 20mm;
  @bottom-left {{
    content: "{footer_left}";
    font-family: 'Inter', sans-serif; font-size: 8pt; color: {_MUTED};
  }}
  @bottom-right {{
    content: "Seite " counter(page) " / " counter(pages);
    font-family: 'Inter', sans-serif; font-size: 8pt; color: {_MUTED};
    font-variant-numeric: tabular-nums;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; color: {_BODY};
        font-size: 10.5pt; line-height: 1.62; margin: 0; }}

/* Briefkopf (nur Seite 1, im Fluss) */
.letterhead {{ display: flex; justify-content: space-between; align-items: flex-start;
  padding-bottom: 12px; border-bottom: 2px solid {_INK}; margin-bottom: 28px; }}
.logo {{ height: 34px; width: auto; }}
.brand {{ font-family: 'Inter Tight', sans-serif; font-weight: 800; font-size: 15pt;
  letter-spacing: -0.02em; color: {_INK}; }}
.brand .dot {{ color: {_RED}; }}
.brand-addr {{ font-size: 8pt; color: {_MUTED}; text-align: right; line-height: 1.55; padding-top: 2px; }}

/* Titelblock */
.kicker {{ font-family: 'Inter', sans-serif; font-weight: 600; font-size: 8.5pt;
  text-transform: uppercase; letter-spacing: 0.18em; color: {_RED}; margin-bottom: 10px; }}
h1 {{ font-family: 'Inter Tight', sans-serif; font-weight: 800; font-size: 25pt;
  line-height: 1.05; letter-spacing: -0.025em; color: {_INK}; margin: 0; }}
.subtitle {{ font-size: 12pt; color: {_BODY}; margin-top: 8px; line-height: 1.4; }}
.rule {{ height: 3px; width: 46px; background: {_RED}; margin: 16px 0 0; }}
.meta {{ margin-top: 16px; padding-top: 10px; border-top: 1px solid {_HAIRLINE};
  font-size: 8.5pt; color: {_MUTED}; display: flex; gap: 14px; flex-wrap: wrap;
  font-variant-numeric: tabular-nums; }}
.meta span::before {{ content: ""; }}

/* Markdown-Body (fett, Listen, Tabellen, Bilder, Zitate, Code) */
.body {{ margin-top: 30px; }}
/* Nichts darf breiter als der Satzspiegel werden: lange Wörter/URLs brechen um. */
.md {{ overflow-wrap: break-word; word-wrap: break-word; }}
.md h1, .md h2, .md h3, .md h4 {{ font-family: 'Inter Tight', sans-serif; color: {_INK};
  letter-spacing: -0.01em; break-after: avoid; }}
.md h1 {{ font-size: 16pt; font-weight: 800; margin: 22px 0 8px; }}
.md h2 {{ font-size: 13pt; font-weight: 700; margin: 20px 0 6px; }}
.md h3 {{ font-size: 11.5pt; font-weight: 700; margin: 16px 0 5px; }}
.md h4 {{ font-size: 10.5pt; font-weight: 700; margin: 14px 0 4px; }}
.md p {{ margin: 0 0 8px; }}
.md ul, .md ol {{ margin: 0 0 8px; padding-left: 20px; }}
.md li {{ margin: 0 0 3px; }}
.md strong {{ font-weight: 700; color: {_INK}; }}
.md em {{ font-style: italic; }}
.md a {{ color: {_RED}; text-decoration: none; }}
.md blockquote {{ margin: 8px 0; padding: 4px 0 4px 14px; border-left: 3px solid {_HAIRLINE}; color: {_MUTED}; }}
.md img {{ max-width: 100%; height: auto; margin: 8px 0; border-radius: 4px; }}
.md code {{ font-family: monospace; font-size: 9pt; background: {_SAND}; padding: 1px 4px; border-radius: 3px; }}
.md pre {{ background: {_SAND}; padding: 10px 12px; border-radius: 6px; break-inside: avoid;
  white-space: pre-wrap; overflow-wrap: break-word; }}
.md pre code {{ background: none; padding: 0; }}
/* table-layout:fixed → die Spalten teilen sich die A4-Breite, Zellinhalt bricht um; die Tabelle
   kann NIE breiter als der Satzspiegel werden (kein Überlauf/Beschnitt über den Rand hinaus). */
.md table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin: 10px 0;
  font-size: 9.5pt; break-inside: avoid; }}
.md th, .md td {{ border: 1px solid {_HAIRLINE}; padding: 6px 9px; text-align: left;
  vertical-align: top; overflow-wrap: break-word; word-wrap: break-word; }}
.md th {{ background: {_SAND}; font-weight: 700; color: {_INK}; }}
.md hr {{ border: none; border-top: 1px solid {_HAIRLINE}; margin: 16px 0; }}

.empty {{ color: {_MUTED}; font-style: italic; }}

/* Freigaben/Unterschriften-Layer */
.signoffs {{ margin-top: 34px; padding-top: 14px; border-top: 2px solid {_INK}; break-inside: avoid; }}
.signoffs-title {{ font-family: 'Inter', sans-serif; font-weight: 600; font-size: 8.5pt;
  text-transform: uppercase; letter-spacing: 0.14em; color: {_RED}; margin-bottom: 12px; }}
.sig-grid {{ display: flex; flex-wrap: wrap; gap: 22px; }}
.sig-cell {{ width: 46%; break-inside: avoid; }}
.sig-line {{ height: 46px; border-bottom: 1px solid {_INK}; display: flex; align-items: flex-end;
  padding-bottom: 3px; }}
.sig-img {{ max-height: 42px; max-width: 100%; }}
.sig-ok {{ color: #15803D; font-weight: 700; font-size: 10pt; }}
.sig-no {{ color: {_RED}; font-weight: 700; font-size: 10pt; }}
.sig-pending {{ color: {_MUTED}; font-style: italic; font-size: 9pt; }}
.sig-name {{ margin-top: 5px; font-size: 9.5pt; font-weight: 700; color: {_INK}; }}
.sig-meta {{ font-size: 8pt; color: {_MUTED}; }}
</style></head><body>
  <div class="letterhead">
    {logo_html}
    <div class="brand-addr">{address_html}</div>
  </div>
  <header>
    <div class="kicker">Dokument</div>
    <h1>{_esc(title)}</h1>
    {f'<div class="subtitle">{_esc(subtitle)}</div>' if subtitle else ''}
    <div class="rule"></div>
    <div class="meta">{''.join(f'<span>{_esc(m)}</span>' for m in meta_bits)}</div>
  </header>
  <div class="body">
    {f'<div class="md">{body_html}</div>' if body_html else '<p class="empty">Dieses Dokument hat noch keinen Inhalt.</p>'}
  </div>
  {_signoffs_html(signoffs)}
</body></html>"""

    return HTML(string=doc).write_pdf()
