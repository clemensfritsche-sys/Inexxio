"""INEXXIO-Wortmarke parametrisch: die Konstruktion des heutigen Logos
(Pfeil-E, Chevron-X, verschachteltes zweites X, roter Schwung), Proportionen als Parameter."""
import math
from shapely.geometry import Polygon, LineString, box, Point
from shapely.ops import unary_union

H = 100.0

def fillet(pts, R, n=10):
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = map(lambda p: complex(*p), pts[i-1:i+2])
        u = (p0 - p1) / abs(p0 - p1); v = (p2 - p1) / abs(p2 - p1)
        th = math.acos(max(-1, min(1, (u.conjugate() * v).real)))
        d = R / math.tan(th / 2)
        a, b = p1 + u * d, p1 + v * d
        bis = (u + v) / abs(u + v)
        c = p1 + bis * (R / math.sin(th / 2))
        a0, a1 = math.atan2((a - c).imag, (a - c).real), math.atan2((b - c).imag, (b - c).real)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for j in range(n + 1):
            ang = a0 + da * j / n
            q = c + R * complex(math.cos(ang), math.sin(ang))
            out.append((q.real, q.imag))
    out.append(pts[-1])
    return out

def build(p):
    s, k, G, g = p["s"], p["k"], p["G"], p["g"]
    a = p.get("a", 0.89 * s)
    t = s * math.sqrt(1 + k * k)
    ink = []
    x = 0
    ink.append(box(0, 0, s, H)); x = s + g                       # I
    wN = p["wN"]; xr = x + wN
    dx = wN - 2 * s; d = s
    for _ in range(20): d = s * math.sqrt(1 + ((H - d) / dx) ** 2)
    ink += [box(x, 0, x + s, H), box(xr - s, 0, xr, H),
            Polygon([(x + s, 0), (xr - s, H - d), (xr - s, H), (x + s, d)])]   # N
    x = xr + g; wE = p["wE"]
    tip = x + wE
    ink += [box(x, 0, x + s, H),
            Polygon([(x, 0), (tip - k * a, 0), (tip, a), (x, a)]),
            Polygon([(x, H - a), (tip, H - a), (tip - k * a, H), (x, H)]),
            box(x, H / 2 - a / 2, x + p.get("mid", 0.86) * wE, H / 2 + a / 2)]  # E
    x1 = tip - k * a + G
    ink.append(Polygon([(x1, 0), (x1 + t, 0), (x1 + t + k * H / 2, H / 2), (x1 + t, H), (x1, H), (x1 + k * H / 2, H / 2)]))  # X1 Chevron
    x2 = x1 + t + G
    fall = Polygon([(x2, 0), (x2 + t, 0), (x2 + t + k * H, H), (x2 + k * H, H)])
    big = 400
    red_band = Polygon([(x2 + k * (H + big), -big), (x2 + t + k * (H + big), -big),
                        (x2 + t + k * (H - (H + big)), H + big), (x2 + k * (H - (H + big)), H + big)])
    # rising band: x_left(y) = x2 + k*(H - y)
    def rx(y, off=0): return x2 + k * (H - y) + off
    cut = Polygon([(rx(-big, -G), -big), (rx(-big, t + G), -big), (rx(H + big, t + G), H + big), (rx(H + big, -G), H + big)])
    ink.append(fall.difference(cut))                                 # X2 fallend, geteilt
    xI = x2 + k * H + t + g
    ink.append(box(xI, 0, xI + s, H))                                 # I
    xO = xI + s + p["gO"]; wO = p["wO"]; so = p.get("so", 1.05 * s); ov = p.get("ov", 1.2)
    if p.get("circle"):
        r = wO / 2; cx = xO + r
        ring = Point(cx, H / 2).buffer(r, 64).difference(Point(cx, H / 2).buffer(r - so, 64))
    else:
        ro = p["ro"]
        outer = box(xO + ro, -ov + ro, xO + wO - ro, H + ov - ro).buffer(ro, 32, join_style=1)
        ri = max(ro - so, 0.01)
        inner = box(xO + so + ri, -ov + so + ri, xO + wO - so - ri, H + ov - so - ri).buffer(ri, 32, join_style=1)
        ring = outer.difference(inner)
        cx = xO + wO / 2
    ink.append(ring)
    # roter Schwung: Mittellinie unten -> Aufstrich -> oben
    b = p["b"]; yb = H + b + s / 2; yt = -b - s / 2
    xs = p.get("start", s / 2); xe = p.get("end", cx)
    mode = p.get("swoosh", "full")
    big = 60
    if mode == "x":
        pts = [(rx(H + big, t / 2), H + big), (rx(-big, t / 2), -big)]
    elif mode == "under":
        pts = [(xs, yb), (rx(yb, t / 2), yb), (rx(-big, t / 2), -big)]
    elif mode == "over":
        pts = [(rx(H + big, t / 2), H + big), (rx(yt, t / 2), yt), (xe, yt)]
    else:
        pts = [(xs, yb), (rx(yb, t / 2), yb), (rx(yt, t / 2), yt), (xe, yt)]
    cl = LineString(fillet(pts, p.get("R", 0.95 * s), 10) if len(pts) > 2 else pts)
    cap = p.get("cap", "round")
    red = cl.buffer(s / 2, 12, cap_style={"round": 1, "flat": 2}[cap], join_style=1)
    lo = 0 if mode in ("x", "under") else -999
    hi = H if mode in ("x", "over") else 999
    red = red.intersection(box(-999, lo, 9999, hi))
    inkU = unary_union(ink)
    r = p.get("soft", 0)
    if r:
        inkU = inkU.buffer(-r, 4).buffer(r, 4).buffer(r, 4).buffer(-r, 4).simplify(0.03)
        red = red.buffer(-r, 4).buffer(r, 4).buffer(r, 4).buffer(-r, 4).simplify(0.03)
    # Symbol: X1 + X2 + Aufstrich als Kapsel
    ext = p.get("symext", 0.32 * H)
    sym_cl = LineString([(rx(H + ext, t / 2), H + ext), (rx(-ext, t / 2), -ext)])
    sym_red = sym_cl.buffer(s / 2, 24, cap_style={"round": 1, "flat": 2}[p.get("symcap", cap)])
    if ext <= 0:
        sym_red = LineString([(rx(H + big, t / 2), H + big), (rx(-big, t / 2), -big)]).buffer(s / 2, 4, cap_style=2).intersection(box(-999, 0, 9999, H))
    sym_ink = unary_union([ink[8], ink[9]])            # X1 (Chevron) + X2
    if r:
        sym_red = sym_red.buffer(-r, 4).buffer(r, 4).simplify(0.03)
        sym_ink = sym_ink.buffer(-r, 4).buffer(r, 4).buffer(r, 4).buffer(-r, 4).simplify(0.03)
    x2 = ink[9]
    if r:
        x2 = x2.buffer(-r, 4).buffer(r, 4).buffer(r, 4).buffer(-r, 4).simplify(0.03)
    p["_x2"] = x2
    return inkU, red, sym_ink, sym_red

def num(v):
    t = f"{v:.1f}".rstrip("0").rstrip(".")
    if t in ("-0", ""): t = "0"
    return t.replace("0.", ".", 1) if t.startswith(("0.", "-0.")) else t

def pair(a, b):
    sb = num(b)
    return num(a) + ("" if sb.startswith("-") else " ") + sb

def d_of(geom, dx=0, dy=0):
    """Kompakter Pfad: absolut starten, dann relative Schritte auf 0.1 Einheit."""
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for pg in polys:
        for ring in [pg.exterior] + list(pg.interiors):
            c = [(round(x + dx, 1), round(y + dy, 1)) for x, y in list(ring.coords)[:-1]]
            parts = ["M" + pair(*c[0]) + "l"]
            steps = []
            for (x0, y0), (x1, y1) in zip(c, c[1:]):
                if (x1, y1) != (x0, y0): steps.append(pair(round(x1 - x0, 1), round(y1 - y0, 1)))
            out.append(parts[0] + "".join(st if st.startswith("-") else " " + st for st in steps).lstrip() + "z")
    return "".join(out)
