"""Bild-Uploads (Fotos) – Speicherung in der DB, Auslieferung per Token.

Bewusst ohne Cloud-Bucket: sofort lauffähig auf Cloud Run, ohne IAM/Bucket-Setup. Der
Schnitt ist so gelegt, dass später NUR dieser Service auf GCS umgestellt werden müsste
(die Verbraucher speichern eine URL, keinen Blob). Bilder werden beim Upload normalisiert:
EXIF-Rotation angewandt, auf eine vernünftige Kantenlänge begrenzt und als JPEG re-kodiert –
so bleibt die DB-Grösse beschränkt und die Anzeige schnell."""

import io
import secrets

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Attachment

_MAX_EDGE = 1600          # längste Kante in px (Foto-Doku / Shop reicht das dicke)
_JPEG_QUALITY = 82
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024   # 20 MB Rohupload-Limit (vor Verkleinerung)
_MAX_PIXELS = 40_000_000   # ~40 MP – Schutz vor Decompression-Bombs (kleine Datei, riesige Fläche)


def _flatten_to_rgb(img):
    """Ein Bild nach RGB bringen und dabei etwaige **Transparenz auf WEISS** legen.

    Kritisch für gezeichnete Unterschriften: die stammen von einem transparenten Canvas
    (dunkle Striche auf transparentem PNG). Ein direktes ``convert("RGB")`` würde die
    transparenten Pixel zu **Schwarz** machen → die ganze Fläche wäre ein schwarzer Balken.
    Darum die Transparenz vorher auf einen weissen Hintergrund komponieren."""
    from PIL import Image
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return img.convert("RGB")


def store_image(db: Session, raw: bytes, filename: str | None, actor_id: int | None) -> Attachment:
    """Rohes Bild normalisieren (EXIF/Grösse/JPEG) und als ``Attachment`` ablegen (flush,
    kein commit – der Aufrufer schliesst ab). Wirft 400 bei ungültigem Bild, 413 zu gross.

    Die GESAMTE Pillow-Verarbeitung liegt im Try (inkl. thumbnail/save), damit ein bösartiges
    Bild nie einen 500/Worker-Crash auslöst, sondern sauber als 400 abgewiesen wird. Zusätzlich
    ein hartes Pixel-Limit gegen Decompression-Bombs (kleine Datei ⇒ Gigapixel-Fläche)."""
    if not raw:
        raise HTTPException(400, detail="Leere Datei")
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="Datei zu gross (max. 20 MB)")
    from PIL import Image, ImageOps
    try:
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        if w * h > _MAX_PIXELS:
            raise HTTPException(413, detail="Bildauflösung zu hoch")
        img = ImageOps.exif_transpose(img)   # Handy-Fotos korrekt drehen
        img = _flatten_to_rgb(img)           # Transparenz auf WEISS (sonst schwarzer Balken)
        img.thumbnail((_MAX_EDGE, _MAX_EDGE))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        data = buf.getvalue()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, detail="Ungültiges oder nicht unterstütztes Bild")
    att = Attachment(
        token=secrets.token_urlsafe(24),
        mime="image/jpeg",
        data=data,
        filename=(filename or None),
        width=img.width,
        height=img.height,
        byte_size=len(data),
        created_by=actor_id,
    )
    db.add(att)
    db.flush()
    return att


def get_by_token(db: Session, token: str) -> Attachment:
    att = db.query(Attachment).filter(
        Attachment.token == token, Attachment.is_active == True).first()
    if not att:
        raise HTTPException(404, detail="Bild nicht gefunden")
    return att


def public_url(att: Attachment) -> str:
    """Relative URL (Token) – die Verbraucher speichern diesen String."""
    return f"/api/v1/attachments/{att.token}"
