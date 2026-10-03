"""Erzeugt die Wortmarke als SVG aus den echten Inter-Glyphen (Gewicht 700).

Einmalig bzw. nach einem Namenswechsel laufen lassen – die Ergebnisse liegen versioniert
in public/logo/. Die Website selbst setzt die Wortmarke als TEXT (Lockup.astro); diese
Dateien sind für JSON-LD, Open Graph und Druck.

    pip install fonttools brotli
    python3 scripts/make-logo.py INEXXIO

Ausgabe:
    public/logo/inexxio-wortmarke.svg        Variante A – schwarz
    public/logo/inexxio-wortmarke-weiss.svg  Variante A – weiss (auf dunkel)
    public/logo/inexxio-wortmarke-b.svg      Variante B – «XX» rot (Alternative)
Status: [[PLATZHALTER: finales Logo]] – bis ein gestaltetes Logo vorliegt.
"""
import sys
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / "src/assets/fonts/inter-latin-wght-normal.woff2"
OUT = HERE.parent / "public/logo"
INK, RED, WHITE = "#0A0A0B", "#E51A14", "#FFFFFF"
TRACKING = -0.035  # em – dieselbe Laufweite wie im Lockup


def _num(n: float) -> str:
    s = f"{n:.1f}"
    return s[:-2] if s.endswith(".0") else s


def glyph_paths(text: str) -> tuple[list[tuple[str, str]], tuple[float, float, float, float]]:
    font = TTFont(str(FONT))
    font = instantiateVariableFont(font, {"wght": 700})
    upem = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    x = 0.0
    out = []
    bounds = BoundsPen(glyphs)
    for i, ch in enumerate(text):
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs, ntos=_num)
        # Y spiegeln (Font: y nach oben, SVG: y nach unten) und an die Position schieben.
        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, -1, x, 0)))
        out.append((ch, pen.getCommands()))
        x += glyphs[name].width + (TRACKING * upem if i < len(text) - 1 else 0)
    return out, bounds.bounds


def svg(text: str, fill: str, red_xx: bool = False) -> str:
    paths, (x0, y0, x1, y1) = glyph_paths(text)
    parts = []
    xx_start = text.find("XX") if red_xx else -1
    for i, (_, d) in enumerate(paths):
        color = RED if red_xx and xx_start <= i < xx_start + 2 else fill
        parts.append(f'<path fill="{color}" d="{d}"/>')
    vb = f"{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="{text}">'
        f"<title>{text}</title>{''.join(parts)}</svg>\n"
    )


def main() -> None:
    text = sys.argv[1] if len(sys.argv) > 1 else "INEXXIO"
    OUT.mkdir(parents=True, exist_ok=True)
    slug = text.lower()
    (OUT / f"{slug}-wortmarke.svg").write_text(svg(text, INK))
    (OUT / f"{slug}-wortmarke-weiss.svg").write_text(svg(text, WHITE))
    (OUT / f"{slug}-wortmarke-b.svg").write_text(svg(text, INK, red_xx=True))
    print(f"Wortmarke «{text}» → {OUT}")


if __name__ == "__main__":
    main()
