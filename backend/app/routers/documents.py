"""Dokumente im ERP – nur für das Personal (``services/documents``, ``services/access``).

Freigeben ist **ein** ``POST`` mit der Datei (oder den gescannten Seiten), Art, Name und
Referenzen. Davor gibt es nichts: der Entwurf lebt im Browser.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..domain import documents as dd
from ..models import Attachment, Document, UserProfile
from ..schemas.documents import (
    DeleteIn, DocumentDetail, DocumentRefOut, DocumentSummary, FiledOut, RecordOut, RefIn,
    SignatureOut,
)
from ..services import access, attachments, documents as docs, people, records

router = APIRouter(prefix="/api/v1/erp/documents", tags=["documents"])


def _preview_url(db: Session, doc: Document) -> Optional[str]:
    url = docs.file_url(db, doc)
    if url is None or not (doc.mime == "application/pdf" or doc.mime.startswith("image/")):
        return None
    return f"{url}/preview"


def summary(db: Session, doc: Document, status: str, q: str = "") -> DocumentSummary:
    return DocumentSummary(object_id=doc.object_id, art=doc.art, name=doc.name, status=status,
                           source=doc.source, mime=doc.mime, created_at=doc.created_at,
                           preview_url=_preview_url(db, doc),
                           snippet=docs.snippet(doc, q) if q else None)


def summaries(db: Session, found: list[Document], q: str = "") -> list[DocumentSummary]:
    sigs = docs.signatures_of(db, (d.id for d in found))
    return [summary(db, d, docs.status_of(d, sigs[d.id]), q) for d in found]


def detail(db: Session, doc: Document) -> DocumentDetail:
    refs = docs.refs_of(db, [doc.id])[doc.id]
    sigs = docs.signatures_of(db, [doc.id])[doc.id]
    names = docs.label_refs(db, refs)
    raw = None
    if doc.file_id is not None and (doc.mime == "text/html" or doc.mime == "application/pdf"):
        raw = db.query(Attachment.data).filter(Attachment.id == doc.file_id).scalar()
    base = summary(db, doc, docs.status_of(doc, sigs))
    return DocumentDetail(
        **base.model_dump(),
        file_url=docs.file_url(db, doc), filename=doc.filename, byte_size=doc.byte_size,
        pages=docs.pdf_pages(raw) if raw and doc.mime == "application/pdf" else None,
        refs=[DocumentRefOut(
            id=r.id, object_id=r.object_id, part=r.part, field=r.field,
            field_label=dd.FIELDS.get(r.field) if r.field else None,
            type=names[r.object_id].type if r.object_id in names else None,
            label=names[r.object_id].label if r.object_id in names else str(r.object_id))
            for r in refs],
        created_by=people.name_by_id(db, doc.created_by),
        deleted_at=doc.deleted_at, deleted_by=people.name_by_id(db, doc.deleted_by),
        delete_reason=doc.delete_reason, delete_problem=docs.delete_problem(db, doc),
        signatures=[SignatureOut(id=s.id, person_object_id=s.person_object_id, name=s.name,
                                 signed_at=s.signed_at, declined_at=s.declined_at,
                                 reason=s.reason) for s in sigs],
        html=raw.decode("utf-8", "replace") if raw and doc.mime == "text/html" else None,
    )


@router.get("", response_model=list[DocumentSummary])
def list_documents(q: str = "", limit: int = 100, offset: int = 0,
                   db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Der Feed «Dokument» – seitenweise, durchsucht auf dem Server (wie die Instanzen)."""
    found = docs.search(db, user, q, limit=max(1, min(limit, 200)), offset=max(0, offset))
    return summaries(db, found, q)


@router.get("/targets", response_model=list[RecordOut])
def search_targets(q: str = "", db: Session = Depends(get_db),
                   _: UserProfile = Depends(require_employee)):
    """Ein Datensatz für eine Referenz – Nummer ODER Name."""
    return [RecordOut(object_id=r.object_id, type=r.type, label=r.label)
            for r in records.search(db, q)]


@router.get("/of/{object_id}", response_model=list[DocumentSummary])
def documents_of(object_id: int, db: Session = Depends(get_db),
                 user: UserProfile = Depends(require_employee)):
    """Die Kacheln unten an einem Datensatz (Regel 4)."""
    return summaries(db, docs.shown_on(db, object_id, user))


@router.get("/{object_id}", response_model=DocumentDetail)
def get_document(object_id: int, db: Session = Depends(get_db),
                 user: UserProfile = Depends(require_employee)):
    return detail(db, docs.readable(db, object_id, user))


@router.post("", response_model=FiledOut, status_code=201)
async def file_document(
    files: list[UploadFile] = File(...),
    art: str = Form(...), name: str = Form(...), source: str = Form("file"),
    refs: str = Form("[]"),
    db: Session = Depends(get_db), user: UserProfile = Depends(require_employee),
):
    """►►► **Freigeben.** ◄◄◄ Eine Datei – oder mehrere gescannte Seiten, die ein PDF werden.
    ``refs`` ist eine JSON-Liste ``[{"object_id": …}]`` (Teil und Feld setzt nur ein Modul)."""
    try:
        wanted = [docs.RefIn(object_id=int(r["object_id"])) for r in json.loads(refs or "[]")]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Die Referenzen sind unlesbar.")
    raws = [await f.read() for f in files]
    if len(raws) > 1:
        raw, mime, filename = docs.pages_to_pdf(raws), "application/pdf", "scan.pdf"
    else:
        raw, mime, filename = raws[0], files[0].content_type or "", files[0].filename
    doc, existed = docs.file(db, raw=raw, filename=filename, mime=mime, art=art, name=name,
                             source=source, refs=wanted, actor=user)
    db.commit()
    if existed and not access.may(user, docs.refs_of(db, [doc.id])[doc.id]):
        raise HTTPException(status_code=409, detail=(
            "Diese Datei gibt es schon als Dokument – du darfst es nicht sehen."))
    return FiledOut(document=detail(db, doc), existed=existed)


@router.post("/{object_id}/refs", response_model=DocumentDetail)
def add_ref(object_id: int, data: RefIn, db: Session = Depends(get_db),
            user: UserProfile = Depends(require_employee)):
    doc = docs.readable(db, object_id, user)
    docs.attach(db, doc, data.object_id, user)
    db.commit()
    return detail(db, doc)


@router.delete("/{object_id}/refs/{ref_id}", response_model=DocumentDetail)
def remove_ref(object_id: int, ref_id: int, db: Session = Depends(get_db),
               user: UserProfile = Depends(require_employee)):
    doc = docs.readable(db, object_id, user)
    docs.detach(db, doc, ref_id, user)
    db.commit()
    return detail(db, doc)


@router.post("/{object_id}/delete", response_model=DocumentDetail)
def delete_document(object_id: int, data: DeleteIn, db: Session = Depends(get_db),
                    user: UserProfile = Depends(require_employee)):
    doc = docs.readable(db, object_id, user)
    docs.delete(db, doc, data.reason, user)
    db.commit()
    return detail(db, doc)
