"""Erzeugt den Logo-Satz INEXXIO (F1) nach ../ – siehe README.md."""
import sys, json, re, io, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from logo import build, d_of
from shapely.ops import unary_union
from shapely import affinity
from svgelements import SVG, Path

INK, RED, W = '#0A0A0B', '#E51A14', '#FFFFFF'
# Proportionen von F1 (Logo-Studie Oktober 2026), Einheit: Versalhoehe = 100
F = {"s": 22.5, "k": 0.85, "G": 13, "g": 13, "a": 20, "wN": 125, "wE": 100, "mid": 0.85, "gO": 12, "wO": 150, "ro": 40, "so": 23.6, "b": 11, "R": 22, "soft": 3.5}
ink, red, _, _ = build(dict(F))
x0, y0, x1, y1 = unary_union([ink, red]).bounds
ink = affinity.translate(ink, -x0, -y0); red = affinity.translate(red, -x0, -y0)
WW, WH = x1 - x0, y1 - y0
cap_top = -y0  # Oberkante der Buchstaben im Zeichen

# Symbol S1: das verschachtelte XX, buendig, kraeftiger gezeichnet
S = dict(F); S.update({'symext': 0, 's': 27, 'G': 16, 'soft': 2.5})
_, _, si, sr = build(S)
sx0, sy0, sx1, sy1 = unary_union([si, sr]).bounds

def f(v): return f'{v:.2f}'.rstrip('0').rstrip('.')

def head(w, h, title, px=None):
    pw = px or w
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(w)} {f(h)}" '
            f'width="{f(pw)}" height="{f(h * pw / w)}"><title>{title}</title>')

def wordmark_paths(ic, rc, dx=0, dy=0, cls=''):
    return (f'<path fill="{ic}" fill-rule="evenodd" d="{d_of(ink, dx, dy)}"/>'
            f'<path fill="{rc}" d="{d_of(red, dx, dy)}"/>')

# «ehemals» und das HS-Steiner-Logo unveraendert aus dem bisherigen Lockup
src = re.sub(r'<metadata>.*</metadata>', '', open(os.path.join(HERE, 'hs-steiner-quelle.svg')).read(), flags=re.S)
paths = [e for e in SVG.parse(io.StringIO(src)).elements() if isinstance(e, Path)]
ehem, hs = paths[2], paths[3]
def placed(p, box_w=None, box_h=None, x=0, y=0):
    bx0, by0, bx1, by1 = p.bbox()
    k = box_w / (bx1 - bx0) if box_w else box_h / (by1 - by0)
    q = Path(p) * f'translate({-bx0},{-by0})'
    q = q * f'scale({k})' * f'translate({x},{y})'
    from logo import num
    d = re.sub(r'-?\d+(?:\.\d+)?', lambda m: num(float(m.group())), q.d())
    d = re.sub(r' (?=-)', '', d)
    return d, (bx1 - bx0) * k, (by1 - by0) * k

# Gestapelt: 60 % Wortmarke, 40 % «ehemals HS Steiner» (Hoehe der Bloecke)
BH = WH * 2 / 3
hs_w = WW * 0.82                   # HS Steiner rechtsbuendig, «ehemals» links daneben
_, _, hs_h = placed(hs, box_w=hs_w)
gap1 = (BH - hs_h) / 2             # Wortmarke -> Linie -> HS Steiner
line_y = WH + gap1
hs_y = line_y + gap1
e_w = WW - hs_w - WW * 0.045
_, _, e_h = placed(ehem, box_w=e_w)
e_y = hs_y + (hs_h - e_h) / 2
e_d, _, _ = placed(ehem, box_w=e_w, x=0, y=e_y)
hs_d, _, _ = placed(hs, box_w=hs_w, x=WW - hs_w, y=hs_y)
SH = hs_y + hs_h
LINE = WH * 0.0046 * 10 / 10

def stacked(ic, rc, gc, lc, lo='1'):
    return (head(WW, SH, 'INEXXIO – ehemals HS Steiner', 460) + wordmark_paths(ic, rc) +
            f'<rect x="0" y="{f(line_y)}" width="{f(WW)}" height="{f(max(WH*0.012,0.6))}" fill="{lc}" fill-opacity="{lo}"/>'
            f'<path fill="{gc}" d="{e_d}"/><path fill="{ic}" d="{hs_d}"/></svg>')

def horizontal(ic, rc):
    return head(WW, WH, 'INEXXIO', 460) + wordmark_paths(ic, rc) + '</svg>'

def square(ic, rc, frac=0.92, bg=None, adaptive=False, rx=22):
    w, h = sx1 - sx0, sy1 - sy0; k = 100 * frac / max(w, h)
    dx, dy = (100 - w * k) / 2 - sx0 * k, (100 - h * k) / 2 - sy0 * k
    sty = ('<style>.k{fill:#0A0A0B}@media (prefers-color-scheme:dark){.k{fill:#FFFFFF}}</style>'
           if adaptive else '')
    kfill = 'class="k"' if adaptive else f'fill="{ic}"'
    b = f'<rect width="100" height="100" rx="{rx}" fill="{bg}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="512" height="512">'
            f'<title>INEXXIO</title>{sty}{b}<g transform="translate({f(dx)} {f(dy)}) scale({k:.4f})">'
            f'<path {kfill} fill-rule="evenodd" d="{d_of(si)}"/><path fill="{rc}" d="{d_of(sr)}"/></g></svg>')

OUT = {
 'inexxio-horizontal-light.svg': horizontal(INK, RED),
 'inexxio-horizontal-dark.svg': horizontal(W, RED),
 'inexxio-horizontal-red.svg': horizontal(W, W),
 'inexxio-horizontal-mono.svg': horizontal(INK, INK),
 'inexxio-stacked-light.svg': stacked(INK, RED, '#5F5C58', '#D1CEC8'),
 'inexxio-stacked-dark.svg': stacked(W, RED, '#A9A6A0', W, '0.2'),
 'inexxio-stacked-red.svg': stacked(W, W, W, W, '0.45'),
 'inexxio-stacked-mono.svg': stacked(INK, INK, INK, INK, '0.25'),
 'inexxio-symbol.svg': square(None, RED, adaptive=True),
 'inexxio-symbol-light.svg': square(INK, RED),
 'inexxio-symbol-dark.svg': square(W, RED),
 'inexxio-symbol-red.svg': square(RED, RED),
 'inexxio-symbol-on-red.svg': square(W, W),
 'inexxio-symbol-mono.svg': square(INK, INK),
 'inexxio-app-icon.svg': square(W, RED, frac=0.66, bg=INK),
}
OUTDIR = os.path.dirname(HERE)
for k, v in OUT.items():
    open(os.path.join(OUTDIR, k), 'w').write(v)
print(f'{len(OUT)} Dateien nach {OUTDIR} · Wortmarke {WW:.1f} x {WH:.1f} · gestapelt {WW:.1f} x {SH:.1f}')
