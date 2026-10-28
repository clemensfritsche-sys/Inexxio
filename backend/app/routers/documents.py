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
    DeleteIn, DocumentDetail, DocumentRefOut, DocumentSummary, FiledOut, ProposalOut,
    ProposedRef, RecordOut, RefIn, RequirementOut, SignatureOut, TargetIn, TemplateIn,
)
from ..services import (access, ai, document, documents as docs, fields, legal, people,
                        reading, records, sites)
from ..services import requirements as reqs

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


def _legal_html(db: Session, doc: Document) -> Optional[str]:
    """Ein Rechtstext aus der Vorlage (Markdown) – gesetzt wie auf der Website, mit den
    Angaben des Betreibers."""
    kind = (doc.facts or {}).get("kind")
    raw = docs.raw_of(db, doc) if doc.mime == legal.MARKDOWN and kind in legal.KINDS else None
    if raw is None:
        return None
    values = legal.of_operator(db)
    text = legal.parse(kind, legal.valid_from_of(doc), legal.fill(raw.decode("utf-8", "replace"), values))
    return document.standalone(text, sender=legal.sender_line(values))


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
        html=(raw.decode("utf-8", "replace") if raw and doc.mime == "text/html"
              else _legal_html(db, doc)),
        read_later=(doc.file_id is not None and not doc.text and ai.ready()
                    and (doc.mime in ai.IMAGE_TYPES or doc.mime == "application/pdf")),
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
    """Die Kacheln unten an einem Datensatz (Regel 4) – je Kachel, welches Pflichtfeld des
    Datensatzes sie füllt (ein Feld zeigt sein Dokument, ohne danach zu suchen)."""
    found = docs.shown_on(db, object_id, user)
    out = summaries(db, found)
    refs = docs.refs_of(db, (d.id for d in found))
    for doc, row in zip(found, out):
        row.fields = [r.field for r in refs[doc.id] if r.object_id == object_id and r.field]
    return out


def _json(raw: str, what: str):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{what} sind unlesbar.")


async def _upload(files: list[UploadFile]) -> tuple[bytes, str, Optional[str]]:
    """Eine Datei – oder mehrere gescannte Seiten, die EIN PDF werden."""
    raws = [await f.read() for f in files]
    if len(raws) > 1:
        return docs.pages_to_pdf(raws), "application/pdf", "scan.pdf"
    return raws[0], files[0].content_type or "", files[0].filename


@router.post("", response_model=FiledOut, status_code=201)
async def file_document(
    files: list[UploadFile] = File(...),
    art: str = Form(...), name: str = Form(...), source: str = Form("file"),
    refs: str = Form("[]"), target: str = Form(""),
    text: str = Form(""), keywords: str = Form(""), facts: str = Form(""),
    db: Session = Depends(get_db), user: UserProfile = Depends(require_employee),
):
    """►►► **Freigeben.** ◄◄◄ ``refs`` ist eine JSON-Liste ``[{"object_id": …}]`` (ganze
    Datensätze); ``target`` ein Pflichtfeld, das in derselben Transaktion gesetzt wird.
    ``text``/``keywords``/``facts`` kommen aus dem Vorschlag – gelesen wird nicht zweimal."""
    try:
        wanted = [docs.RefIn(object_id=int(r["object_id"])) for r in (_json(refs, "Die Referenzen") or [])]
        aim = TargetIn(**_json(target, "Das Feld")) if target else None
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Die Referenzen sind unlesbar.")
    raw, mime, filename = await _upload(files)
    doc, existed = docs.file(db, raw=raw, filename=filename, mime=mime, art=art, name=name,
                             source=source, refs=wanted, actor=user, text=text or None,
                             keywords=keywords or None, facts=_json(facts, "Die Angaben"))
    if existed and not access.may(user, docs.refs_of(db, [doc.id])[doc.id]):
        raise HTTPException(status_code=409, detail=(
            "Diese Datei gibt es schon als Dokument – du darfst es nicht sehen."))
    if existed and wanted:
        docs.add_refs(db, doc, wanted, user)
    if aim is not None:
        fields.apply(db, actor=user, doc=doc, object_id=aim.object_id, part=aim.part,
                     field=aim.field, extra=aim.extra)
    db.commit()
    return FiledOut(document=detail(db, doc), existed=existed)


@router.post("/read", response_model=ProposalOut)
async def read_draft(
    files: list[UploadFile] = File(...),
    sender: Optional[int] = Form(None), hint: str = Form(""),
    db: Session = Depends(get_db), user: UserProfile = Depends(require_employee),
):
    """►►► **Einen Entwurf lesen – ohne ihn zu speichern.** ◄◄◄ Die KI schlägt Art, Name und
    Referenz vor; ohne KI kommt ein leerer Vorschlag (Absender als Referenz, wenn bekannt)."""
    raw, mime, _ = await _upload(files)
    p = reading.propose(db, raw=raw, mime=docs._sniff(raw, mime), actor=user,
                        sender_object_id=sender, hint=hint or None)
    db.commit()     # das Log des KI-Aufrufs
    return ProposalOut(art=p.art, name=p.name, text=p.text, keywords=p.keywords, facts=p.facts,
                       refs=[ProposedRef(**r.__dict__) for r in p.refs], why=p.why, read=p.read,
                       ai=ai.ready(), values=p.values, requirement=p.requirement)


@router.get("/requirements", response_model=list[RequirementOut])
def open_requirements(db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Worauf Module warten (``services/requirements``) – je Anforderung ein Satz."""
    return [RequirementOut(key=r.key, label=r.label, sentence=r.sentence, fields=list(r.fields),
                           object_id=r.object_id, part=r.part, field=r.field)
            for r in reqs.open_for(db, user)]


@router.post("/template", response_model=DocumentDetail)
def from_template(data: TemplateIn, db: Session = Depends(get_db),
                  user: UserProfile = Depends(require_employee)):
    """**«Aus Vorlage»** – AGB oder Datenschutz einer eigenen Gesellschaft aus der Vorlage
    (``legal.from_template``); nur der Admin. Ein Mensch entscheidet, nie der Start."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Rechtstexte setzt nur der Admin.")
    company = sites.require_own(db, data.company)
    doc = legal.from_template(db, company, data.kind, user)
    db.commit()
    return detail(db, doc)


@router.post("/{object_id}/field", response_model=DocumentDetail)
def set_field(object_id: int, data: TargetIn, db: Session = Depends(get_db),
              user: UserProfile = Depends(require_employee)):
    """Ein schon freigegebenes Dokument in ein Pflichtfeld – ändern, nie leeren."""
    doc = docs.readable(db, object_id, user)
    fields.apply(db, actor=user, doc=doc, object_id=data.object_id, part=data.part,
                 field=data.field, extra=data.extra)
    db.commit()
    return detail(db, doc)


@router.post("/{object_id}/read", response_model=DocumentDetail)
def read_later(object_id: int, db: Session = Depends(get_db),
               user: UserProfile = Depends(require_employee)):
    """**Das Lesen nachholen** – für ein Dokument, das ohne KI freigegeben wurde. Schreibt nur
    Text, Stichworte und Angaben; Art, Name und Referenz bleiben, wie der Mensch sie setzte."""
    doc = docs.readable(db, object_id, user)
    if doc.text or doc.file_id is None:
        return detail(db, doc)
    from ..models import Attachment
    raw = db.query(Attachment.data).filter(Attachment.id == doc.file_id).scalar()
    p = reading.propose(db, raw=raw, mime=doc.mime, actor=user)
    if p.read:
        doc.text, doc.keywords, doc.facts = p.text or None, p.keywords or None, p.facts or None
    db.commit()
    return detail(db, doc)


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


# Zuletzt: «/{object_id}» fängt sonst «/requirements» ab.
@router.get("/{object_id}", response_model=DocumentDetail)
def get_document(object_id: int, db: Session = Depends(get_db),
                 user: UserProfile = Depends(require_employee)):
    return detail(db, docs.readable(db, object_id, user))
