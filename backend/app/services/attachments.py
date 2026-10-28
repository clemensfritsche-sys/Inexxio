"""**Der Korb** – jede Datei, abgelegt in **Cloud Storage**, ausgeliefert per Token.

Zwei Wege hinein: ``store_raw`` legt die Datei eines Dokuments unverändert ab (die eine
Ablage, ``services/documents``); ``store_image`` normalisiert ein Bild, das kein Dokument
ist (die Unterschrift, die Fotos einer Anfrage).

**Wo die Bytes liegen, weiss nur dieser Dienst** (``keep`` · ``bytes_of`` · ``discard``):
im Bucket der Umgebung (``FILES_BUCKET``, Objektname = Token, privat) – die Zeile hält dann
nur Name, Sorte, Grösse. Ohne Bucket (lokal, Tests) oder wenn er gerade nicht schreibbar ist,
bleiben sie in der Zeile (``data``) – eine Datei geht nie verloren, weil der Speicher hakt.
Gelesen wird beides gleich. Die Verbraucher kennen nur die URL ``/api/v1/attachments/{token}``.
"""

import io
import secrets
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import Attachment

_MAX_EDGE = 1600          # längste Kante in px (für eine Foto-Doku reicht das dicke)
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
        filename=(filename or None),
        width=img.width,
        height=img.height,
        byte_size=len(data),
        created_by=actor_id,
    )
    keep(att, data)
    db.add(att)
    db.flush()
    return att


#: **Ein Dokument darf jede Datei sein** – bis zu dieser Grösse. Cloud Run nimmt höchstens
#: 32 MB je Anfrage an; darunter bleibt Luft für den Rest des Formulars.
MAX_FILE_BYTES = 25 * 1024 * 1024


def store_raw(db: Session, raw: bytes, filename: str | None, mime: str,
              actor_id: int | None) -> Attachment:
    """**Eine Datei unverändert in den Korb** – für Dokumente (PDF, Bild, Tabelle, Video …).
    Ein Dokument ist das Original; verkleinert wird nichts."""
    if not raw:
        raise HTTPException(400, detail="Leere Datei")
    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(413, detail="Datei zu gross (max. 25 MB)")
    att = Attachment(token=secrets.token_urlsafe(24), mime=(mime or "application/octet-stream")[:100],
                     filename=(filename or None), byte_size=len(raw), created_by=actor_id)
    keep(att, raw)
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
    return public_url_of(att.token)


def public_url_of(token: str) -> str:
    return f"/api/v1/attachments/{token}"


#: Was der Browser direkt zeigen darf. Alles andere (HTML, SVG, Office …) geht mit einer
#: Sandbox hinaus: eine hochgeladene Datei darf auf unserer Adresse nie ein Skript ausführen.
INLINE_SAFE = ("image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf")


#: ►►► **Eine Datei ist privat** – wer den Link hat, sieht sie; ein geteilter Zwischenspeicher
#: (das CDN von Firebase Hosting, ein Proxy) behält sie nie. ``public`` nur, was ohnehin
#: öffentlich ist (die Rechtstexte der Website, ``documents.is_public_file``).
PRIVATE_CACHE = "private, max-age=86400"
PUBLIC_CACHE = "public, max-age=31536000, immutable"


def serve_headers(att: Attachment, *, public: bool = False) -> dict[str, str]:
    headers = {"Cache-Control": PUBLIC_CACHE if public else PRIVATE_CACHE,
               "X-Content-Type-Options": "nosniff"}
    if att.mime not in INLINE_SAFE:
        headers["Content-Security-Policy"] = "sandbox"
    if att.filename:
        from urllib.parse import quote
        headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(att.filename)}"
    return headers


# ---------------------------------------------------------------------------
# Wo die Bytes liegen – Cloud Storage, sonst die Zeile
# ---------------------------------------------------------------------------

_client = None
#: In einem Lauf, der zurückgerollt wird (Vorschau eines Belegs), geht nichts in den Bucket –
#: sonst bliebe dort eine Datei ohne Zeile liegen.
_IN_DATABASE: ContextVar[bool] = ContextVar("attachments_in_database", default=False)


def bucket():
    """Der Bucket dieser Umgebung – oder ``None`` (keiner gesetzt)."""
    name = get_settings().files_bucket
    if not name:
        return None
    global _client
    if _client is None:
        from google.cloud import storage
        _client = storage.Client()
    return _client.bucket(name)


@contextmanager
def in_database():
    """Was hier entsteht, bleibt in der Zeile – für einen Lauf, der zurückgerollt wird."""
    token = _IN_DATABASE.set(True)
    try:
        yield
    finally:
        _IN_DATABASE.reset(token)


def keep(att: Attachment, raw: bytes) -> None:
    """**Die Bytes ablegen** – im Bucket, sonst in der Zeile. Ein Fehler des Speichers kostet
    nie die Datei: sie bleibt dann in der Datenbank, und das Log sagt es."""
    target = None if _IN_DATABASE.get() else bucket()
    if target is not None:
        try:
            target.blob(att.token).upload_from_string(raw, content_type=att.mime)
            att.data = None
            return
        except Exception as exc:                                   # noqa: BLE001
            print(f"WARNING: Cloud Storage nicht schreibbar ({exc!r}) – Datei bleibt in der DB.",
                  flush=True)
    att.data = raw


def bytes_of(att: Attachment) -> bytes:
    """**Die Bytes einer Datei** – aus der Zeile oder aus dem Bucket."""
    if att.data is not None:
        return bytes(att.data)
    target = bucket()
    if target is None:
        raise HTTPException(503, detail="Die Datei liegt im Speicher, der hier nicht eingerichtet ist.")
    try:
        return target.blob(att.token).download_as_bytes()
    except Exception as exc:                                       # noqa: BLE001
        if type(exc).__name__ == "NotFound":
            raise HTTPException(404, detail="Diese Datei gibt es nicht mehr.")
        print(f"WARNING: Cloud Storage nicht lesbar ({exc!r})", flush=True)
        raise HTTPException(503, detail="Die Datei ist gerade nicht erreichbar – bitte gleich noch einmal.")


def discard(db: Session, att: Attachment) -> None:
    """**Eine Datei löschen** – die Zeile, und erst nach dem Commit das Objekt im Bucket (rollt
    die Transaktion zurück, ist die Datei noch da)."""
    if att.data is None and bucket() is not None:
        name = att.token

        def _drop(_session) -> None:
            try:
                bucket().blob(name).delete()
            except Exception as exc:                               # noqa: BLE001
                print(f"WARNING: Objekt {name} nicht gelöscht ({exc!r})", flush=True)
        event.listen(db, "after_commit", _drop, once=True)
    db.delete(att)
