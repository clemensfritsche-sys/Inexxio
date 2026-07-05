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


def _paragraphs(body: str) -> str:
    """Fliesstext eines Abschnitts in Absätze zerlegen (Leerzeilen/Zeilenumbrüche)."""
    if not body:
        return ""
    blocks = [b.strip() for b in str(body).replace("\r\n", "\n").split("\n") if b.strip()]
    return "".join(f"<p>{_esc(b)}</p>" for b in blocks)


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return _esc(value) if value else ""


def _obj_nr(object_id: Optional[int]) -> str:
    return str(object_id).zfill(9) if object_id else "—"


def _address_lines(company: dict) -> list[str]:
    """Saubere, mehrzeilige Firmen-Anschrift für den Briefkopf (nur befüllte Zeilen)."""
    street = " ".join(str(x) for x in [company.get("street"), company.get("street_nr")] if x)
    place = " ".join(str(x) for x in [company.get("zip_code"), company.get("city")] if x)
    contact = " · ".join(str(x) for x in [company.get("email"), company.get("phone")] if x)
    ids = " · ".join(str(x) for x in [
        f"UID {company.get('uid_number')}" if company.get("uid_number") else None,
        f"MWST {company.get('vat_number')}" if company.get("vat_number") else None,
    ] if x)
    lines = [company.get("company_name") or "Inexxio", street, place,
             company.get("country"), contact, ids]
    return [str(x) for x in lines if x]


def render_pdf(content: dict, *, company: dict | None = None,
               object_id: Optional[int] = None, issued_at=None) -> bytes:
    """Ein Dokument (kanonischer ``content``) als markengetreues A4-PDF rendern.

    ``object_id`` = Instanz-Objektnummer (die Dokumentennummer), ``issued_at`` =
    Instanz-Freigabedatum. Beides kann beim Entwurf noch fehlen (Vorschau)."""
    from weasyprint import HTML

    company = company or {}
    address_html = "<br>".join(_esc(ln) for ln in _address_lines(company))
    logo_html = (f'<img class="logo" src="{_LOGO_FILE.as_uri()}" alt="">'
                 if _LOGO_FILE.exists()
                 else f'<div class="brand">{_esc(company.get("company_name") or "Inexxio")}'
                      f'<span class="dot">.</span></div>')

    title = content.get("title") or "Dokument"
    subtitle = content.get("subtitle")
    sections = content.get("sections") or []

    # Meta: Nummer = Instanz-Objektnummer, Datum = Instanz-Freigabe. Keine Version, kein «gültig ab».
    meta_bits = [f"Nr. {_obj_nr(object_id)}" if object_id else "Entwurf"]
    if issued_at:
        meta_bits.append(f"Datum {_fmt_date(issued_at)}")

    sections_html = "".join(
        f"<section class='clause'><h2>{_esc(s.get('heading') or '')}</h2>"
        f"{_paragraphs(s.get('body') or '')}</section>"
        for s in sections
    )

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

/* Abschnitte */
.body {{ margin-top: 30px; }}
.clause {{ margin-bottom: 20px; }}
.clause h2 {{ font-family: 'Inter Tight', sans-serif; font-weight: 700; font-size: 12.5pt;
  color: {_INK}; letter-spacing: -0.01em; margin: 0 0 6px; break-after: avoid; }}
.clause p {{ margin: 0 0 8px; }}
.clause p:last-child {{ margin-bottom: 0; }}

.empty {{ color: {_MUTED}; font-style: italic; }}
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
    {sections_html or '<p class="empty">Dieses Dokument hat noch keinen Inhalt.</p>'}
  </div>
</body></html>"""

    return HTML(string=doc).write_pdf()
