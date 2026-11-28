"""►►► **Das Bild in der Unterschrift – EINE Stelle.** ◄◄◄

Jede Mail unterschreibt mit einem Bild (``mail_layout._avatar``): dem Profilbild des
Menschen, sonst dem Bild des Postfachs, sonst den Initialen. Hier wird daraus **ein ruhiges,
quadratisches Bild**, das die Mail rund zeigt (``border-radius``; Outlook am Computer eckig) –
das Gesicht in der Mitte, ohne Bewegung (Inhaber 28.11.2026: «Wie ein Brief»; die schrägen
Streifen von früher sind weg).

Die Adresse (``url``) ist ein **signierter Link** (``core/signed``): er trägt die Quelle des
Fotos und die Initialen selbst, ohne Tabelle, ohne Ablauf – eine Mail von heute zeigt ihr
Bild auch in zehn Jahren. Gerechnet wird beim ersten Abruf und dann vom CDN (Firebase
Hosting) gehalten; ist das Foto nicht zu holen, stehen die Initialen da (kurz gehalten,
damit das Foto beim nächsten Abruf wieder kommt). Ältere Mails fragen dieselbe Adresse mit
``.gif`` – sie bekommen dasselbe Bild.
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
#: Grösse in der Mail (rund); gerechnet wird dreimal so gross (scharf auf jedem Bildschirm).
SIZE = 56
_PX = SIZE * 3
#: Die Initialen: weiss auf ruhigem Grau – trägt hell wie dunkel (Grau-600 des Design Systems).
SURFACE, ON_SURFACE = (94, 96, 100), (255, 255, 255)
MAX_BYTES = 5_000_000


def initials(name: str) -> str:
    return "".join(w[0] for w in (name or "").split()[:2]).upper()


def url(photo: str, name: str) -> str:
    """Die Adresse des Bilds – für ``<img src>`` in der Mail."""
    token = signed.sign({"p": photo or "", "i": initials(name)}, PURPOSE)
    return f"{get_settings().frontend_base_url.rstrip('/')}{PATH}{token}.jpg"


def read(token: str) -> tuple[str, str]:
    """Quelle und Initialen aus der Adresse – oder ``signed.BadLink``."""
    data = signed.read(token, PURPOSE)
    return str(data.get("p") or ""), str(data.get("i") or "")[:2]


def _larger(photo: str) -> str:
    """Google liefert Profilbilder klein (``=s96-c``); scharf braucht es grösser."""
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


def render(photo: Optional[Image.Image], letters: str) -> bytes:
    """Das Bild als JPEG: das Foto quadratisch, das Gesicht in der Mitte – oder die Initialen."""
    if photo is not None:
        im = ImageOps.fit(photo, (_PX, _PX), Image.LANCZOS, centering=(0.5, 0.4))
    else:
        im = Image.new("RGB", (_PX, _PX), SURFACE)
        try:
            font = ImageFont.load_default(size=int(_PX * 0.38))
        except TypeError:     # ältere Pillow ohne skalierbare Standardschrift
            font = ImageFont.load_default()
        ImageDraw.Draw(im).text((_PX / 2, _PX / 2), letters, fill=ON_SURFACE, font=font,
                                anchor="mm")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue()


#: Gerechnete Bilder je Adresse – nur solche mit Foto (oder ohne Foto gewollt); die
#: Initialen als Ersatz für ein Foto, das nicht kam, werden beim nächsten Abruf neu versucht.
_DONE: dict[str, bytes] = {}
_KEEP = 64


def image(token: str) -> tuple[bytes, bool]:
    """Das Bild zur Adresse und ob es so bleibt (``False``: Initialen, weil das Foto nicht
    kam – kurz halten). ``signed.BadLink``, wenn die Adresse nicht von uns ist."""
    if token in _DONE:
        return _DONE[token], True
    photo, letters = read(token)
    picture = fetch(photo) if photo else None
    data, final = render(picture, letters), picture is not None or not photo
    if final:
        if len(_DONE) >= _KEEP:
            _DONE.pop(next(iter(_DONE)))
        _DONE[token] = data
    return data, final
