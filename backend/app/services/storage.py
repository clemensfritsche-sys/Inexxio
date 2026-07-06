"""Blob-Ablage für hochgeladene Dokumente (PDF/Bilder) – GCS mit DB-Fallback.

EINE Stelle, an der die Bytes gespeichert/gelesen/gelöscht werden. Ist ein
``gcs_bucket`` konfiguriert, landen die Dateien in Google Cloud Storage (Cloud-Run-
ADC-Auth, kein Key); sonst als Fallback in der DB-Tabelle ``document_blobs`` – so
läuft das Modul auch ohne Bucket/IAM sofort (analog «payments_provider=manual»).

Wichtig: hier wird – anders als bei ``attachments`` (Fotos → JPEG) – **nichts
normalisiert/re-kodiert**. Ein Beleg-PDF muss byte-genau erhalten bleiben (Rechtsbeleg,
10-Jahres-Archivierung). Die Auslieferung ist NICHT öffentlich (Rechnungen!) – der
Router streamt authentifiziert (``routers/document_files.py``)."""

import hashlib
import secrets
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import DocumentBlob

settings = get_settings()

MAX_UPLOAD_BYTES = 30 * 1024 * 1024   # 30 MB – Belege/Manuals liegen darunter

# MIME → Dateiendung (für einen sprechenden Storage-Key / Download-Namen).
_EXT = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/tiff": ".tif",
}


def _ext_for(mime: str, filename: str | None) -> str:
    if mime in _EXT:
        return _EXT[mime]
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()[:8]
    return ""


@lru_cache
def _gcs_bucket():
    """GCS-Bucket lazy & einmalig (ADC-Auth). Import erst hier, damit ein fehlendes
    Paket/keine Config die App nie am Start hindert."""
    try:
        from google.cloud import storage as gcs
    except Exception as e:  # pragma: no cover
        raise HTTPException(503, detail=f"GCS-Client nicht verfügbar: {e}")
    try:
        client = gcs.Client()
        return client.bucket(settings.gcs_bucket)
    except Exception as e:
        raise HTTPException(503, detail=f"GCS nicht erreichbar: {type(e).__name__}")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store(db: Session, data: bytes, mime: str, filename: str | None) -> dict:
    """Bytes ablegen und Metadaten zurückgeben (``flush``, kein commit – Aufrufer schliesst ab).

    Rückgabe: ``{storage_key, storage_backend, byte_size, sha256}``."""
    if not data:
        raise HTTPException(400, detail="Leere Datei")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="Datei zu gross (max. 30 MB)")
    digest = hash_bytes(data)
    key = f"{settings.gcs_document_prefix}/{digest[:2]}/{secrets.token_urlsafe(18)}{_ext_for(mime, filename)}"
    # GCS, wenn ein Bucket konfiguriert ist – aber NIE hart scheitern: klappt der Upload nicht
    # (Bucket fehlt, Service-Account ohne Rechte, Netz), fällt DIESE Datei auf die DB zurück.
    # Der tatsächliche Ablageort steht je Datei am ``storage_backend`` → das Lesen findet die
    # Bytes immer korrekt. So ist das Setzen von ``GCS_BUCKET`` gefahrlos (kein Deploy-Ordering).
    if settings.gcs_bucket:
        try:
            _gcs_bucket().blob(key).upload_from_string(data, content_type=mime)
            return {"storage_key": key, "storage_backend": "gcs", "byte_size": len(data), "sha256": digest}
        except Exception as e:
            print(f"WARNING: GCS-Upload fehlgeschlagen ({type(e).__name__}) – Fallback in die DB. "
                  f"Bucket/Service-Account-Rechte prüfen.", flush=True)
    db.add(DocumentBlob(storage_key=key, mime=mime, data=data, byte_size=len(data)))
    db.flush()
    return {"storage_key": key, "storage_backend": "db", "byte_size": len(data), "sha256": digest}


def read(db: Session, storage_key: str, backend: str) -> tuple[bytes, str]:
    """Bytes + MIME laden (404, wenn weg). Backend wird pro Datei am ``DocumentFile`` geführt."""
    if backend == "gcs":
        blob = _gcs_bucket().blob(storage_key)
        try:
            data = blob.download_as_bytes()
        except Exception:
            raise HTTPException(404, detail="Datei nicht gefunden")
        return data, (blob.content_type or "application/octet-stream")
    row = db.query(DocumentBlob).filter(DocumentBlob.storage_key == storage_key).first()
    if not row:
        raise HTTPException(404, detail="Datei nicht gefunden")
    return row.data, row.mime


def delete(db: Session, storage_key: str, backend: str) -> None:
    """Bytes best-effort entfernen (bei einem abgelehnten/verworfenen Upload). Nie werfen –
    ein verwaister Blob ist harmlos, ein Fehler hier soll den Ablauf nicht brechen."""
    try:
        if backend == "gcs":
            _gcs_bucket().blob(storage_key).delete()
        else:
            db.query(DocumentBlob).filter(DocumentBlob.storage_key == storage_key).delete()
            db.flush()
    except Exception as e:
        print(f"WARNING: storage.delete({storage_key}) failed: {e}", flush=True)
