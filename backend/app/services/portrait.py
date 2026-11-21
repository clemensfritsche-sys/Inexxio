"""►►► **Das Bild in der Unterschrift – EINE Stelle.** ◄◄◄

Jede Mail unterschreibt mit einem Bild (``mail_layout._avatar``): dem Profilbild des
Menschen, sonst dem Bild des Postfachs, sonst den Initialen. Hier wird daraus das Bild des
Hauses – **in schrägen Streifen, die sich einmal öffnen** (Gestaltung im Artefakt
«INEXXIO Mail-Signatur», Variante B):

* Feine rote Linien zeichnen sich, öffnen sich zum Foto; links bleibt **eine** rote Kante.
* **Einmal**, gut eine Sekunde, dann steht das Bild – keine Schleife.
* **Ein GIF**: das einzige bewegte Bild, das jedes Mailprogramm zeigt (CSS-Animation
  ignorieren Gmail und Outlook). **Das erste Bild ist das fertige** – Outlook unter Windows
  zeigt nur dieses.
* **Durchsichtig** zwischen den Streifen – dasselbe Bild trägt im hellen und im dunklen
  Modus (gerechnet in doppelter Grösse, das Mailprogramm glättet beim Verkleinern).

Die Adresse (``url``) ist ein **signierter Link** (``core/signed``): er trägt die Quelle des
Fotos und die Initialen selbst, ohne Tabelle, ohne Ablauf – eine Mail von heute zeigt ihr
Bild auch in zehn Jahren. Gerechnet wird beim ersten Abruf und dann vom CDN (Firebase
Hosting) gehalten; ist das Foto nicht zu holen, stehen die Initialen da (kurz gehalten,
damit das Foto beim nächsten Abruf wieder kommt).
"""

import io
import re
import urllib.request
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..core import signed
from ..core.config import get_settings

PURPOSE = "portrait"
PATH = "/api/v1/mail/portrait/"
#: Grösse in der Mail; gerechnet wird doppelt so gross (scharf auf jedem Bildschirm).
WIDTH, HEIGHT = 116, 96
_W, _H = WIDTH * 2, HEIGHT * 2
#: Schräge: oben liegt ein Streifen um so viel weiter rechts als unten.
_SLANT = 0.26 * _W
#: Die Streifen – (links, rechts) an der Unterkante als Anteil der Breite, (oben, unten) als
#: Anteil der Höhe. Der erste, dünne ist die rote Kante.
STRIPS = ((0.00, 0.03, .45, .80), (0.05, 0.27, .20, .97), (0.29, 0.55, .03, 1.0),
          (0.57, 0.80, .00, .92), (0.82, 0.97, .16, .74))
RED = (200, 20, 15)                 # das Rot des Logos (``mail_layout.RED_TEXT``)
SURFACE, ON_SURFACE = (92, 95, 102), (255, 255, 255)   # trägt hell wie dunkel
STEP, LINE, OPEN = 0.11, 0.30, 0.45                    # Takt in Sekunden
FRAME_MS, HOLD_MS = 40, 600_000
MAX_BYTES = 5_000_000


def initials(name: str) -> str:
    return "".join(w[0] for w in (name or "").split()[:2]).upper()


def url(photo: str, name: str) -> str:
    """Die Adresse des Bilds – für ``<img src>`` in der Mail."""
    token = signed.sign({"p": photo or "", "i": initials(name)}, PURPOSE)
    return f"{get_settings().frontend_base_url.rstrip('/')}{PATH}{token}.gif"


def read(token: str) -> tuple[str, str]:
    """Quelle und Initialen aus der Adresse – oder ``signed.BadLink``."""
    data = signed.read(token, PURPOSE)
    return str(data.get("p") or ""), str(data.get("i") or "")[:2]


def _larger(photo: str) -> str:
    """Google liefert Profilbilder klein (``=s96-c``); für die Streifen grösser holen."""
    if "googleusercontent.com" in photo:
        return re.sub(r"=s\d+(-c)?$", "", photo) + "=s400-c"
    return photo


def fetch(photo: str) -> Optional[Image.Image]:
    """Das Foto – oder ``None``, wenn es nicht zu holen oder kein Bild ist."""
    if not photo.startswith("https://"):
        return None
    try:
        with urllib.request.urlopen(_larger(photo), timeout=5) as res:   # noqa: S310 – signiert
            data = res.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
        return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception:     # jede Störung heisst: Initialen statt Foto
        return None


def _scene(photo: Optional[Image.Image], letters: str) -> Image.Image:
    """Was durch die Streifen zu sehen ist – das Foto (gefüllt, Gesicht oben) oder die
    Initialen auf ruhiger Fläche."""
    if photo is not None:
        return ImageOps.fit(photo, (_W, _H), Image.LANCZOS, centering=(0.47, 0.35))
    im = Image.new("RGB", (_W, _H), SURFACE)
    try:
        font = ImageFont.load_default(size=int(_H * 0.36))
    except TypeError:     # ältere Pillow ohne skalierbare Standardschrift
        font = ImageFont.load_default()
    ImageDraw.Draw(im).text((_W * 0.47, _H * 0.52), letters, fill=ON_SURFACE, font=font,
                            anchor="mm")
    return im


def _quad(x0: float, x1: float, top: float, bottom: float) -> list[tuple[float, float]]:
    def at(x: float, y: float) -> tuple[float, float]:
        return (x * (_W - _SLANT) + _SLANT * (1 - y), y * _H)
    return [at(x0, bottom), at(x1, bottom), at(x1, top), at(x0, top)]


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _frame(scene: Image.Image, t: float) -> Image.Image:
    """Ein Bild der Bewegung zum Zeitpunkt ``t`` (Sekunden) – durchsichtig, wo nichts ist."""
    im = Image.new("RGBA", (_W, _H), (0, 0, 0, 0))
    red = Image.new("RGBA", (_W, _H), RED + (255,))
    photo = scene.convert("RGBA")
    for i, (x0, x1, top, bottom) in enumerate(STRIPS):
        line = _ease((t - i * STEP) / LINE)
        opened = _ease((t - i * STEP - 0.22) / OPEN)
        grow = bottom - (bottom - top) * line
        if i == 0:                  # die rote Kante: zeichnet sich und bleibt
            if line > 0:
                _paint(im, red, _quad(x0, x1, grow, bottom))
            continue
        if line > 0 and opened < 1:
            _paint(im, red, _quad(x0, x0 + 0.012, grow, bottom))
        if opened > 0:
            _paint(im, photo, _quad(x0, x0 + (x1 - x0) * opened, top, bottom))
    return im


def _paint(im: Image.Image, src: Image.Image, poly: list[tuple[float, float]]) -> None:
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    im.paste(src, (0, 0), mask)


def _gif(frames: list[Image.Image], durations: list[int]) -> bytes:
    """Ein GIF aus durchsichtigen Bildern – jedes ersetzt das vorige ganz (``disposal=2``)."""
    buf = io.BytesIO()
    frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:],
                   duration=durations, disposal=2)
    return buf.getvalue()


def render(photo: Optional[Image.Image], letters: str) -> bytes:
    """Das Bild als GIF: zuerst das fertige (Outlook), dann einmal die Bewegung, dann Ruhe."""
    scene = _scene(photo, letters)
    end = (len(STRIPS) - 1) * STEP + 0.22 + OPEN
    steps = int(end * 1000 / FRAME_MS) + 1
    frames = [_frame(scene, 99)] + [_frame(scene, i * FRAME_MS / 1000) for i in range(steps)]
    durations = [20] + [FRAME_MS] * (steps - 1) + [HOLD_MS]
    return _gif(frames, durations)


#: Gerechnete Bilder je Adresse – nur solche mit Foto (oder ohne Foto gewollt); die
#: Initialen als Ersatz für ein Foto, das nicht kam, werden beim nächsten Abruf neu versucht.
_DONE: dict[str, bytes] = {}
_KEEP = 64


def gif(token: str) -> tuple[bytes, bool]:
    """Das Bild zur Adresse und ob es so bleibt (``False``: Initialen, weil das Foto nicht
    kam – kurz halten). ``signed.BadLink``, wenn die Adresse nicht von uns ist."""
    if token in _DONE:
        return _DONE[token], True
    photo, letters = read(token)
    image = fetch(photo) if photo else None
    data, final = render(image, letters), image is not None or not photo
    if final:
        if len(_DONE) >= _KEEP:
            _DONE.pop(next(iter(_DONE)))
        _DONE[token] = data
    return data, final
