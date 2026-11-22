"""►►► Die Weltkarte des ERP erzeugen – `src/lib/world-map.ts` (nicht von Hand ändern). ◄◄◄

Je Land (ISO-2) ein SVG-Pfad und sein Mittelpunkt, dazu die Ankerpunkte der Regionen für die
Beschriftung der Gebietskarte. Quelle: Natural Earth 1:50m (gemeinfrei) über das npm-Paket
`world-atlas`, die Ländercodes aus `i18n-iso-countries`; Projektion Equal Earth (flächentreu),
ohne Antarktis; Linien vereinfacht (Douglas-Peucker).

    npm pack world-atlas@2.0.2 i18n-iso-countries@7.14.0   # in einem leeren Ordner, entpacken
    python3 scripts/world-map.py <world-atlas>/package/countries-50m.json \\
        <i18n-iso-countries>/package/codes.json src/lib/world-map.ts
"""
import json
import math
import sys

TOPO, CODES, OUT = sys.argv[1:4]
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
W_OUT = 1000.0
EPS = 0.25          # Vereinfachung in Karteneinheiten


def equal_earth(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    th = math.asin(M * math.sin(phi))
    t2 = th * th
    t6 = t2 * t2 * t2
    x = lam * math.cos(th) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


X0, _ = equal_earth(-180, 0)
X1, _ = equal_earth(180, 0)
_, Y0 = equal_earth(0, 84)
_, Y1 = equal_earth(0, -57)
S = W_OUT / (X1 - X0)
W, H = W_OUT, (Y0 - Y1) * S


def pj(lon: float, lat: float) -> tuple[float, float]:
    x, y = equal_earth(max(-180, min(180, lon)), max(-57, min(84, lat)))
    return (x - X0) * S, (Y0 - y) * S


def dp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1e-9
    i, m = 0, 0.0
    for k in range(1, len(pts) - 1):
        d = abs(dy * (pts[k][0] - a[0]) - dx * (pts[k][1] - a[1])) / n
        if d > m:
            i, m = k, d
    if m < eps:
        return [a, b]
    return dp(pts[:i + 1], eps)[:-1] + dp(pts[i:], eps)


iso = {row[2]: row[0] for row in json.load(open(CODES))}      # numerisch → alpha-2
NAMED = {"Kosovo": "XK", "N. Cyprus": "CY", "Somaliland": "SO"}
t = json.load(open(TOPO))
sc, tr = t["transform"]["scale"], t["transform"]["translate"]
arcs = []
for a in t["arcs"]:
    x = y = 0
    pts = []
    for dx_, dy_ in a:
        x += dx_
        y += dy_
        pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
    arcs.append(pts)


def ring(r):
    out = []
    for ai in r:
        seg = arcs[ai] if ai >= 0 else list(reversed(arcs[~ai]))
        out.extend(seg if not out else seg[1:])
    return out


f = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")
paths: dict[str, str] = {}
centers: dict[str, list[float]] = {}
best: dict[str, float] = {}
for g in t["objects"]["countries"]["geometries"]:
    code = iso.get(str(g.get("id"))) or NAMED.get((g.get("properties") or {}).get("name", ""))
    if not code or code == "AQ" or g["type"] not in ("Polygon", "MultiPolygon"):
        continue
    polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
    parts = []
    for poly in polys:
        lonlat = ring(poly[0])
        # Ringe über die Datumsgrenze (Fidschi, Tschukotka) auf eine Seite legen.
        if max(p[0] for p in lonlat) - min(p[0] for p in lonlat) > 180:
            lonlat = [(lo + 360 if lo < 0 else lo, la) for lo, la in lonlat]
            lonlat = [(min(lo, 180), la) for lo, la in lonlat]
        raw = [pj(lo, la) for lo, la in lonlat]
        h = len(raw) // 2
        pts = dp(raw[:h + 1], EPS)[:-1] + dp(raw[h:], EPS)
        if len(pts) < 3:
            continue
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area < 1.5:
            continue
        if area > best.get(code, -1):
            best[code] = area
            centers[code] = [round(sum(xs) / len(xs), 1), round(sum(ys) / len(ys), 1)]
        parts.append("M" + "L".join(f(x) + "," + f(y) for x, y in pts) + "Z")
    if parts:
        paths[code] = paths.get(code, "") + "".join(parts)

# Wo der Name einer Region auf der Karte steht (Länge, Breite) – nur Beschriftung.
ANCHORS = {"NAM": (-102, 48), "LATAM": (-62, -12), "EUR": (14, 54), "AFR": (19, 4),
           "MEA": (46, 29), "ASIA": (98, 42), "OCE": (134, -26)}
anchors = {k: [round(c, 1) for c in pj(*v)] for k, v in ANCHORS.items()}
# Ausschnitte: die ganze Welt und Europa (Länge −12…36, Breite 34…63).
ex0, ey0 = pj(-12, 63)
ex1, ey1 = pj(36, 34)
views = {"world": [0, 0, round(W), round(H)],
         "europe": [round(ex0, 1), round(ey0, 1), round(ex1 - ex0, 1), round(ey1 - ey0, 1)]}
data = {"w": round(W), "h": round(H), "paths": paths, "centers": centers, "anchors": anchors,
        "views": views}
open(OUT, "w").write(
    "/**\n * Die Weltkarte des ERP – je Land (ISO-2) ein SVG-Pfad und sein Mittelpunkt, dazu die\n"
    " * Ankerpunkte der Regionen. Erzeugt von `scripts/world-map.py` aus Natural Earth 1:50m\n"
    " * (gemeinfrei), Projektion Equal Earth. Nicht von Hand ändern.\n */\n"
    "export const WORLD: { w: number; h: number; paths: Record<string, string>; "
    "centers: Record<string, [number, number]>; anchors: Record<string, [number, number]>; "
    "views: Record<'world' | 'europe', [number, number, number, number]> } = "
    + json.dumps(data, separators=(",", ":")) + ";\n")
print(len(paths), sum(len(v) for v in paths.values()), round(W), round(H))
