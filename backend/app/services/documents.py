"""►►► **Dokumente – die drei Schreibstellen und ihre Ableitungen.** ◄◄◄

* ``file`` gibt frei: Datei in den Korb, Nummer, Art, Name, Referenzen – in einem Schritt.
  Vorher gibt es nichts (Regel 2). Dieselbe Datei zweimal ist dasselbe Dokument (Regel 1).
* ``attach`` / ``detach`` / ``set_field`` ändern Referenzen. Eine Referenz aus einem
  Pflichtfeld entfernt man nie hier, sondern ändert sie dort, wo das Feld steht (Regel 6).
* ``delete`` löscht, was nirgends hängt (Regel 8): Datei und Text sind weg, der Datensatz
  bleibt mit Art, Name, wer, wann, Grund.

Jede schreibt ins ``audit_log``. Sonst schreibt niemand in diese Tabellen. Wer was sieht,
entscheidet ``services/access`` – hier wird nur gefragt.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from ..domain import documents as dd
from ..models import Attachment, Document, DocumentRef, DocumentSignature, UserProfile
from . import access, attachments, objects, records
from .admin import log_audit


@dataclass(frozen=True)
class RefIn:
    """Eine Referenz, wie sie gesetzt wird."""

    object_id: int
    part: Optional[str] = None
    field: Optional[str] = None


# ---------------------------------------------------------------------------
# Lesen
# ---------------------------------------------------------------------------

def refs_of(db: Session, doc_ids: Iterable[int]) -> dict[int, list[DocumentRef]]:
    ids = set(doc_ids)
    out: dict[int, list[DocumentRef]] = {i: [] for i in ids}
    if not ids:
        return out
    for r in (db.query(DocumentRef).filter(DocumentRef.document_id.in_(ids),
                                           DocumentRef.is_active.is_(True))
              .order_by(DocumentRef.id).all()):
        out[r.document_id].append(r)
    return out


def signatures_of(db: Session, doc_ids: Iterable[int]) -> dict[int, list[DocumentSignature]]:
    ids = set(doc_ids)
    out: dict[int, list[DocumentSignature]] = {i: [] for i in ids}
    if not ids:
        return out
    for s in (db.query(DocumentSignature).filter(DocumentSignature.document_id.in_(ids))
              .order_by(DocumentSignature.id).all()):
        out[s.document_id].append(s)
    return out


def status_of(doc: Document, sigs: list[DocumentSignature]) -> str:
    return dd.status(dd.Facts(
        deleted=doc.deleted_at is not None, requested=len(sigs),
        signed=sum(1 for s in sigs if s.signed_at), declined=sum(1 for s in sigs if s.declined_at)))


def by_object_id(db: Session, object_id: int) -> Document:
    doc = db.query(Document).filter(Document.object_id == object_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Ein Dokument {objects.obj_nr(object_id)} "
                                                    f"gibt es nicht.")
    return doc


def readable(db: Session, object_id: int, viewer: UserProfile) -> Document:
    """Ein Dokument, das ``viewer`` sehen darf – sonst 404 (wer es nicht sehen darf, erfährt
    auch nicht, dass es es gibt)."""
    doc = by_object_id(db, object_id)
    if not access.may(viewer, refs_of(db, [doc.id])[doc.id]):
        raise HTTPException(status_code=404, detail=f"Ein Dokument {objects.obj_nr(object_id)} "
                                                    f"gibt es nicht.")
    return doc


def file_url(db: Session, doc: Document) -> Optional[str]:
    if doc.file_id is None:
        return None
    att = db.query(Attachment.token).filter(Attachment.id == doc.file_id).first()
    return attachments.public_url_of(att[0]) if att else None


def shown_on(db: Session, object_id: int, viewer: UserProfile) -> list[Document]:
    """►►► **Regel 4: Ein Dokument erscheint genau dort, wohin seine Referenz zeigt.** ◄◄◄
    Keine Vererbung – auch nicht von der Person zur Firma."""
    q = (db.query(Document).join(DocumentRef, DocumentRef.document_id == Document.id)
         .filter(DocumentRef.object_id == object_id, DocumentRef.is_active.is_(True),
                 Document.deleted_at.is_(None)))
    return access.visible(q, viewer).distinct().order_by(Document.object_id).all()


def search(db: Session, viewer: UserProfile, q: str = "", *, limit: int = 100,
           offset: int = 0) -> list[Document]:
    """►►► **Die Suche – reine Datenbank, kein KI-Aufruf.** ◄◄◄ Nummer, Art und Name als
    Teilstring; der gelesene Text und die Stichworte (Deutsch und Englisch, beim Lesen von der
    KI geschrieben) über den Volltext. Geht darum auch ohne KI."""
    query = access.visible(db.query(Document), viewer)
    q = (q or "").strip()
    if q:
        like = f"%{q.lower()}%"
        words = " & ".join(w for w in "".join(c if c.isalnum() else " " for c in q).split())
        tests = [func.cast(Document.object_id, String).like(f"%{q}%"),
                 func.lower(Document.art).like(like), func.lower(Document.name).like(like),
                 func.lower(func.coalesce(Document.keywords, "")).like(like)]
        if words:
            tests.append(func.to_tsvector("simple", func.coalesce(Document.text, "") + " " +
                                          func.coalesce(Document.keywords, ""))
                         .op("@@")(func.to_tsquery("simple", words + ":*")))
        query = query.filter(or_(*tests))
    return query.order_by(Document.object_id.desc()).offset(offset).limit(limit).all()


def snippet(doc: Document, q: str) -> Optional[str]:
    """Wo im gelesenen Text das Gesuchte steht – ein Ausschnitt für die Trefferliste."""
    q = (q or "").strip().lower()
    text = doc.text or ""
    if not q or not text:
        return None
    at = text.lower().find(q.split()[0])
    if at < 0:
        return None
    start = max(0, at - 40)
    return ("… " if start else "") + " ".join(text[start:at + 80].split()) + " …"


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------

def _sniff(raw: bytes, mime: str) -> str:
    """Die Sorte an den ersten Bytes – nicht am Dateinamen."""
    if raw[:5] == b"%PDF-":
        return "application/pdf"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return (mime or "application/octet-stream").split(";")[0].strip()[:100]


def _check_refs(db: Session, refs: list[RefIn]) -> list[RefIn]:
    out: list[RefIn] = []
    for r in refs:
        if r.part is not None and not dd.PART.match(r.part):
            raise HTTPException(status_code=400, detail=f"«{r.part}» ist kein Teil eines Datensatzes.")
        if r.field is not None and r.field not in dd.FIELDS:
            raise HTTPException(status_code=400, detail=f"Ein Pflichtfeld «{r.field}» gibt es nicht.")
        if objects.resolve_object_type(db, r.object_id) is None:
            raise HTTPException(status_code=400, detail=(
                f"Einen Datensatz {objects.obj_nr(r.object_id)} gibt es nicht."))
        if r not in out:
            out.append(r)
    return out


def file(db: Session, *, raw: bytes, filename: Optional[str], mime: str, art: str, name: str,
         source: str, refs: list[RefIn], actor: Optional[UserProfile],
         on_behalf: Optional[str] = None, text: Optional[str] = None,
         keywords: Optional[str] = None, facts: Optional[dict] = None,
         stored: Optional[Attachment] = None) -> tuple[Document, bool]:
    """►►► **Freigeben – die einzige Stelle, an der ein Dokument entsteht.** ◄◄◄

    Gibt ``(Dokument, schon_da)`` zurück: dieselbe Datei ein zweites Mal legt nichts an,
    sondern liefert das vorhandene (Regel 1). Art und Name sind Pflicht – ohne KI tippt sie
    der Mensch (Regel 3); die Referenz darf leer sein.

    Ohne ``actor`` gibt das System frei (ein Beleg, den die Partei über ihren Link auslöst;
    die Übernahme beim Start). ``stored`` übernimmt eine Datei, die schon im Korb liegt,
    statt sie ein zweites Mal abzulegen."""
    art, name = dd.clean(art, dd.ART_MAX), dd.clean(name, dd.NAME_MAX)
    if not art or not name:
        raise HTTPException(status_code=400, detail="Ohne Art und Name lässt sich nichts freigeben.")
    if source not in dd.SOURCES:
        raise HTTPException(status_code=400, detail=f"Eine Quelle «{source}» gibt es nicht.")
    digest = hashlib.sha256(raw or b"").hexdigest()
    same = (db.query(Document).filter(Document.sha256 == digest,
                                      Document.deleted_at.is_(None)).first())
    if same is not None:
        return same, True
    refs = _check_refs(db, refs)
    mime = _sniff(raw, mime)
    by = actor.id if actor is not None else None
    att = stored if stored is not None else attachments.store_raw(db, raw, filename, mime, by)
    doc = Document(object_id=objects.next_object_id(db, "document"), art=art, name=name,
                   source=source, file_id=att.id, mime=mime, filename=filename or None,
                   byte_size=len(raw), sha256=digest, created_by=by,
                   text=(text or None) and text[:20000], keywords=(keywords or None) and keywords[:4000],
                   facts=facts or None)
    db.add(doc)
    db.flush()
    for r in refs:
        db.add(DocumentRef(document_id=doc.id, object_id=r.object_id, part=r.part,
                           field=r.field, created_by=by))
    db.flush()
    log_audit(db, "documents", "freigegeben", dd.title(art, name), by,
              object_id=doc.object_id, on_behalf=on_behalf or (None if actor else "system"))
    return doc, False


def add_refs(db: Session, doc: Document, refs: list[RefIn], actor: Optional[UserProfile]) -> None:
    """Referenzen an ein **vorhandenes** Dokument – wenn dieselbe Datei ein zweites Mal kommt
    (Regel 1) und doch dorthin gehört, wohin die zweite Freigabe zeigte."""
    have = {(r.object_id, r.part, r.field) for r in refs_of(db, [doc.id])[doc.id]}
    for r in _check_refs(db, refs):
        if (r.object_id, r.part, r.field) not in have:
            db.add(DocumentRef(document_id=doc.id, object_id=r.object_id, part=r.part,
                               field=r.field, created_by=actor.id if actor else None))
    db.flush()


def raw_of(db: Session, doc: Optional[Document]) -> Optional[bytes]:
    """Die Datei eines Dokuments – oder ``None`` (gelöscht)."""
    if doc is None or doc.file_id is None:
        return None
    from . import attachments
    att = db.query(Attachment).filter(Attachment.id == doc.file_id).first()
    return attachments.bytes_of(att) if att is not None else None


def attach(db: Session, doc: Document, object_id: int, actor: UserProfile) -> DocumentRef:
    """**Eine Referenz von Hand** – auf einen ganzen Datensatz. Teile setzt nur ein Feld."""
    if doc.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Ein gelöschtes Dokument hängt nirgends mehr an.")
    (ref_in,) = _check_refs(db, [RefIn(object_id=object_id)])
    found = (db.query(DocumentRef).filter(
        DocumentRef.document_id == doc.id, DocumentRef.object_id == object_id,
        DocumentRef.part.is_(None), DocumentRef.field.is_(None),
        DocumentRef.is_active.is_(True)).first())
    if found is not None:
        return found
    ref = DocumentRef(document_id=doc.id, object_id=object_id, created_by=actor.id)
    db.add(ref)
    db.flush()
    log_audit(db, "documents", "referenz", objects.obj_nr(object_id), actor.id,
              object_id=doc.object_id)
    return ref


def detach(db: Session, doc: Document, ref_id: int, actor: UserProfile) -> None:
    """Eine Referenz entfernen – ausser ihr Datensatz braucht sie (Regel 6)."""
    ref = (db.query(DocumentRef).filter(DocumentRef.id == ref_id, DocumentRef.document_id == doc.id,
                                        DocumentRef.is_active.is_(True)).first())
    if ref is None:
        raise HTTPException(status_code=404, detail="Diese Referenz gibt es nicht (mehr).")
    if ref.field:
        raise HTTPException(status_code=409, detail=(
            f"Das ist ein Pflichtfeld ({dd.FIELDS.get(ref.field, ref.field)}) – geändert wird es "
            f"dort, nie leer."))
    ref.is_active = False
    db.flush()
    log_audit(db, "documents", "referenz", None, actor.id, object_id=doc.object_id,
              old_value=objects.obj_nr(ref.object_id))


def set_field(db: Session, *, document_object_id: int, object_id: int, part: Optional[str],
              field: str, actor: Optional[UserProfile], on_behalf: Optional[str] = None
              ) -> Document:
    """►►► **Ein Pflichtfeld setzen oder ändern – nie leeren.** ◄◄◄ Das Feld zeigt danach auf
    dieses Dokument; ein vorheriges verliert die Referenz (und lässt sich dann löschen)."""
    doc = by_object_id(db, document_object_id)
    if doc.deleted_at is not None:
        raise HTTPException(status_code=409, detail=(
            f"Dokument {objects.obj_nr(doc.object_id)} ist gelöscht."))
    _check_refs(db, [RefIn(object_id=object_id, part=part, field=field)])
    old = (db.query(DocumentRef).filter(
        DocumentRef.object_id == object_id, DocumentRef.field == field,
        (DocumentRef.part == part) if part else DocumentRef.part.is_(None),
        DocumentRef.is_active.is_(True)).all())
    if any(r.document_id == doc.id for r in old):
        return doc
    for r in old:
        r.is_active = False
    db.add(DocumentRef(document_id=doc.id, object_id=object_id, part=part, field=field,
                       created_by=actor.id if actor else None))
    db.flush()
    log_audit(db, "documents", field, objects.obj_nr(doc.object_id),
              actor.id if actor else None, object_id=object_id, on_behalf=on_behalf)
    return doc


def field_document(db: Session, object_id: int, field: str,
                   part: Optional[str] = None) -> Optional[Document]:
    """Welches Dokument steht in diesem Pflichtfeld?"""
    q = (db.query(Document).join(DocumentRef, DocumentRef.document_id == Document.id)
         .filter(DocumentRef.object_id == object_id, DocumentRef.field == field,
                 DocumentRef.is_active.is_(True)))
    q = q.filter(DocumentRef.part == part) if part else q.filter(DocumentRef.part.is_(None))
    return q.order_by(DocumentRef.id.desc()).first()


def delete_problem(db: Session, doc: Document) -> Optional[str]:
    """Warum sich dieses Dokument (noch) nicht löschen lässt – oder ``None``."""
    if doc.deleted_at is not None:
        return "Es ist schon gelöscht."
    if refs_of(db, [doc.id])[doc.id]:
        return "Erst die Referenz entfernen – gelöscht wird nur, was nirgends hängt."
    return None


def delete(db: Session, doc: Document, reason: str, actor: UserProfile) -> None:
    """►►► **Löschen – nur, was nirgends hängt (Regel 8).** ◄◄◄ Die Datei und alles Gelesene
    sind danach weg, auch die Unterschriftsbilder; der Datensatz bleibt im Feed mit Art, Name,
    wer, wann und Grund. Offene Links zeigen «nicht mehr verfügbar»."""
    problem = delete_problem(db, doc)
    if problem:
        raise HTTPException(status_code=409, detail=problem)
    reason = dd.clean(reason, dd.REASON_MAX)
    if not reason:
        raise HTTPException(status_code=400, detail="Gelöscht wird mit Grund.")
    att = db.query(Attachment).filter(Attachment.id == doc.file_id).first() if doc.file_id else None
    for s in db.query(DocumentSignature).filter(DocumentSignature.document_id == doc.id).all():
        s.image = None
    doc.file_id, doc.sha256, doc.text, doc.keywords, doc.facts = None, None, None, None, None
    doc.deleted_at, doc.deleted_by, doc.delete_reason = datetime.now(timezone.utc), actor.id, reason
    if att is not None:
        from . import attachments
        db.flush()
        attachments.discard(db, att)
    db.flush()
    log_audit(db, "documents", "gelöscht", reason, actor.id, object_id=doc.object_id)


# ---------------------------------------------------------------------------
# Vorschaubild – abgeleitet, nie gespeichert
# ---------------------------------------------------------------------------

def pdf_pages(raw: bytes) -> Optional[int]:
    try:
        import pypdfium2 as pdfium
        return len(pdfium.PdfDocument(raw))
    except Exception:
        return None


def preview_png(raw: bytes, mime: str, width: int = 360) -> Optional[bytes]:
    """**Die erste Seite als kleines Bild** – für die Kacheln. Bei Bildern das Bild selbst,
    bei einem PDF die erste Seite; sonst nichts (die Kachel zeigt dann die Sorte)."""
    try:
        from PIL import Image
        if mime == "application/pdf":
            import pypdfium2 as pdfium
            page = pdfium.PdfDocument(raw)[0]
            img = page.render(scale=width / max(page.get_width(), 1)).to_pil()
        elif mime.startswith("image/") and mime != "image/svg+xml":
            img = Image.open(io.BytesIO(raw))
            img.thumbnail((width, width * 2))
        else:
            return None
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return None


def label_refs(db: Session, refs: list[DocumentRef]) -> dict[int, records.Record]:
    return records.labels(db, (r.object_id for r in refs))


def pages_to_pdf(pages: list[bytes]) -> bytes:
    """**Gescannte Seiten werden ein PDF** – Seite für Seite, in der Reihenfolge des Scans."""
    from PIL import Image, ImageOps
    imgs = []
    for raw in pages:
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
            imgs.append(img.convert("RGB"))
        except Exception:
            raise HTTPException(status_code=400, detail="Eine Seite ist kein lesbares Bild.")
    if not imgs:
        raise HTTPException(status_code=400, detail="Keine Seite.")
    buf = io.BytesIO()
    imgs[0].save(buf, format="PDF", save_all=True, append_images=imgs[1:], resolution=150)
    return buf.getvalue()
