"""Dokumente im ERP – nur für das Personal (``services/documents``, ``services/access``).

Freigeben ist **ein** ``POST`` mit der Datei (oder den gescannten Seiten), Art, Name und
Referenzen. Davor gibt es nichts: der Entwurf lebt im Browser.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import DB
from ..domain import documents as dd
from ..models import Document, UserProfile
from ..schemas.documents import (
    DeleteIn, DocumentDetail, DocumentRefOut, DocumentSummary, FiledOut, ProposalOut,
    ProposedRef, RecordOut, RefIn, RequirementOut, SendIn, SignatureOut, SignerOut, TargetIn,
    TemplateIn, ComposeIn, ComposeOut,
)
from ..services import log
from ..services import (access, ai, composing, a4, documents as docs, fields, legal,
                        people, reading, record_labels, signing, sites)
from ..services import requirements as reqs
from ..domain.errors import Conflict, Invalid
from ..domain import policy

router = APIRouter(prefix="/api/v1/erp/documents", tags=["documents"])


def _preview_url(doc: Document, url: Optional[str]) -> Optional[str]:
    if url is None or not (doc.mime == "application/pdf" or doc.mime.startswith("image/")):
        return None
    return f"{url}/preview"


def summary(db: Session, doc: Document, status: str, q: str = "", *,
            urls: Optional[dict[int, str]] = None) -> DocumentSummary:
    url = (urls if urls is not None else docs.file_urls(db, [doc])).get(doc.id)
    return DocumentSummary(object_id=doc.object_id, art=doc.art, name=doc.name, status=status,
                           source=doc.source, mime=doc.mime, created_at=doc.created_at,
                           preview_url=_preview_url(doc, url),
                           snippet=docs.snippet(doc, q) if q else None)


def summaries(db: Session, found: list[Document], q: str = "") -> list[DocumentSummary]:
    """Die Kacheln – Unterschriften und Datei-Links je in EINER Abfrage für alle."""
    sigs = docs.signatures_of(db, (d.id for d in found))
    urls = docs.file_urls(db, found)
    return [summary(db, d, docs.status_of(d, sigs[d.id]), q, urls=urls) for d in found]


def _legal_html(db: Session, doc: Document) -> Optional[str]:
    """Ein Rechtstext aus der Vorlage (Markdown) – gesetzt wie auf der Website, mit den
    Angaben des Betreibers."""
    kind = (doc.facts or {}).get("kind")
    raw = docs.raw_of(db, doc) if doc.mime == legal.MARKDOWN and kind in legal.KINDS else None
    if raw is None:
        return None
    values = legal.of_operator(db)
    text = legal.parse(kind, legal.valid_from_of(doc), legal.fill(raw.decode("utf-8", "replace"), values))
    return a4.standalone(text, sender=legal.sender_line(values))


def detail(db: Session, doc: Document) -> DocumentDetail:
    refs = docs.refs_of(db, [doc.id])[doc.id]
    sigs = docs.signatures_of(db, [doc.id])[doc.id]
    names = docs.label_refs(db, refs)
    raw = None
    if doc.file_id is not None and (doc.mime == "text/html" or doc.mime == "application/pdf"):
        raw = docs.raw_of(db, doc)
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
        html=(signing.signed_html(raw.decode("utf-8", "replace"), sigs)
              if raw and doc.mime == "text/html" else _legal_html(db, doc)),
        read_later=(docs.unread(doc) and ai.ready()
                    and (doc.mime in ai.IMAGE_TYPES or doc.mime == "application/pdf")),
    )


@router.get("", response_model=list[DocumentSummary])
def list_documents(q: str = "", limit: int = 100, offset: int = 0,
                   db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Der Feed «Dokument» – seitenweise, durchsucht auf dem Server (wie die Instanzen)."""
    found = docs.search(db, user, q, limit=max(1, min(limit, 200)), offset=max(0, offset))
    return summaries(db, found, q)


@router.get("/targets", response_model=list[RecordOut])
def search_targets(q: str = "", db: Session = DB,
                   _: UserProfile = Depends(require_employee)):
    """Ein Datensatz für eine Referenz – Nummer ODER Name."""
    return [RecordOut(object_id=r.object_id, type=r.type, label=r.label)
            for r in record_labels.search(db, q)]


@router.get("/of/{object_id}", response_model=list[DocumentSummary])
def documents_of(object_id: int, db: Session = DB,
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
        raise Invalid(f"{what} sind unlesbar.")


def _upload(files: list[UploadFile]) -> tuple[bytes, str, Optional[str]]:
    """Eine Datei – oder mehrere gescannte Seiten, die EIN PDF werden (die Handler sind
    ``def``: gelesen wird synchron aus der gepufferten Datei, im Threadpool)."""
    raws = [f.file.read() for f in files]
    if len(raws) > 1:
        return docs.pages_to_pdf(raws), "application/pdf", "scan.pdf"
    return raws[0], files[0].content_type or "", files[0].filename


@router.post("", response_model=FiledOut, status_code=201)
def file_document(
    files: list[UploadFile] = File(...),
    art: str = Form(...), name: str = Form(...), source: str = Form("file"),
    refs: str = Form("[]"), target: str = Form(""), signers: str = Form("[]"),
    text: str = Form(""), keywords: str = Form(""), facts: str = Form(""),
    db: Session = DB, user: UserProfile = Depends(require_employee),
):
    """►►► **Freigeben.** ◄◄◄ ``refs`` ist eine JSON-Liste ``[{"object_id": …}]`` (ganze
    Datensätze); ``target`` ein Pflichtfeld, das in derselben Transaktion gesetzt wird.
    ``text``/``keywords``/``facts`` kommen aus dem Vorschlag – gelesen wird nicht zweimal."""
    try:
        wanted = [docs.RefIn(object_id=int(r["object_id"])) for r in (_json(refs, "Die Referenzen") or [])]
        aim = TargetIn(**_json(target, "Das Feld")) if target else None
        signing_ids = [int(x) for x in (_json(signers, "Die Unterzeichner") or [])]
    except (KeyError, TypeError, ValueError):
        raise Invalid("Die Referenzen sind unlesbar.")
    raw, mime, filename = _upload(files)
    doc, existed = docs.file(db, raw=raw, filename=filename, mime=mime, art=art, name=name,
                             source=source, refs=wanted, actor=user, text=text or None,
                             keywords=keywords or None, facts=_json(facts, "Die Angaben"))
    if existed and not access.may(user, docs.refs_of(db, [doc.id])[doc.id]):
        raise Conflict("Diese Datei gibt es schon als Dokument – du darfst es nicht sehen.")
    if existed and wanted:
        docs.add_refs(db, doc, wanted, user)
    if signing_ids:
        signing.request(db, doc, signing_ids, user)
    if aim is not None:
        fields.apply(db, actor=user, doc=doc, object_id=aim.object_id, part=aim.part,
                     field=aim.field, extra=aim.extra)
    db.flush()
    return FiledOut(document=detail(db, doc), existed=existed)


@router.post("/read", response_model=ProposalOut)
def read_draft(
    files: list[UploadFile] = File(...),
    sender: Optional[int] = Form(None), hint: str = Form(""),
    db: Session = DB, user: UserProfile = Depends(require_employee),
):
    """►►► **Einen Entwurf lesen – ohne ihn zu speichern.** ◄◄◄ Die KI schlägt Art, Name und
    Referenz vor; ohne KI kommt ein leerer Vorschlag (Absender als Referenz, wenn bekannt)."""
    raw, mime, _ = _upload(files)
    p = reading.propose(db, raw=raw, mime=docs.sniff(raw, mime), actor=user,
                        sender_object_id=sender, hint=hint or None)
    db.flush()
    return ProposalOut(art=p.art, name=p.name, text=p.text, keywords=p.keywords, facts=p.facts,
                       refs=[ProposedRef(**r.__dict__) for r in p.refs], why=p.why, read=p.read,
                       ai=ai.ready(), ai_problem="" if p.read else ai.problem(),
                       values=p.values, requirement=p.requirement)


@router.get("/requirements", response_model=list[RequirementOut])
def open_requirements(db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Worauf Module warten (``services/requirements``) – je Anforderung ein Satz."""
    return [RequirementOut(key=r.key, label=r.label, sentence=r.sentence, fields=list(r.fields),
                           object_id=r.object_id, part=r.part, field=r.field)
            for r in reqs.open_for(db, user)]


@router.post("/compose", response_model=ComposeOut)
def compose(data: ComposeIn, db: Session = DB,
            user: UserProfile = Depends(require_employee)):
    """**Eine Runde Verfassen** (``services/composing``) – gespeichert wird nichts; nur der
    Aufruf der KI steht im Log."""
    current = None
    if data.current:
        try:
            current = composing.Paper(**data.current)
        except ValueError:
            current = None
    paper = composing.compose(db, actor=user, turns=[composing.Turn(**t.model_dump()) for t in data.turns],
                              current=current)
    db.flush()
    if paper is None:
        return ComposeOut(ai=ai.available(db), reply=ai.problem() or (
            "Gerade kann ich nicht schreiben – versuchen Sie es gleich noch einmal."))
    signers = composing.signers_of(db, paper.signers)
    return ComposeOut(reply=paper.reply, paper=paper.model_dump(), art=paper.art, name=paper.name,
                      html=composing.render(db, paper, [(x["object_id"], x["name"]) for x in signers]),
                      signers=[SignerOut(**x) for x in signers])


@router.post("/{object_id}/send", response_model=DocumentDetail)
def send(object_id: int, data: SendIn, db: Session = DB,
         user: UserProfile = Depends(require_employee)):
    """**Senden** – je Empfänger ein Link ohne Ablauf und eine Mail; mit ``sign`` sollen sie
    unterschreiben (``services/signing``)."""
    doc = docs.readable(db, object_id, user)
    if data.sign:
        signing.request(db, doc, data.to, user)
    signing.send(db, doc, data.to, data.note, user)
    db.flush()
    return detail(db, doc)


@router.post("/template", response_model=DocumentDetail)
def from_template(data: TemplateIn, db: Session = DB,
                  user: UserProfile = Depends(require_employee)):
    """**«Aus Vorlage»** – AGB oder Datenschutz einer eigenen Gesellschaft aus der Vorlage
    (``legal.from_template``); nur der Admin. Ein Mensch entscheidet, nie der Start."""
    policy.require(user, "company.legal")
    company = sites.require_own(db, data.company)
    doc = legal.from_template(db, company, data.kind, user)
    db.flush()
    return detail(db, doc)


@router.post("/{object_id}/field", response_model=DocumentDetail)
def set_field(object_id: int, data: TargetIn, db: Session = DB,
              user: UserProfile = Depends(require_employee)):
    """Ein schon freigegebenes Dokument in ein Pflichtfeld – ändern, nie leeren."""
    doc = docs.readable(db, object_id, user)
    fields.apply(db, actor=user, doc=doc, object_id=data.object_id, part=data.part,
                 field=data.field, extra=data.extra)
    db.flush()
    return detail(db, doc)


@router.post("/{object_id}/read", response_model=DocumentDetail)
def read_later(object_id: int, db: Session = DB,
               user: UserProfile = Depends(require_employee)):
    """**Das Lesen nachholen** – für ein Dokument, das ohne KI freigegeben wurde. Schreibt nur
    Text, Stichworte und Angaben; Art, Name und Referenz bleiben, wie der Mensch sie setzte."""
    doc = docs.readable(db, object_id, user)
    if not docs.unread(doc):
        return detail(db, doc)
    raw = docs.raw_of(db, doc)
    p = reading.propose(db, raw=raw, mime=doc.mime, actor=user)
    if p.read:
        # ``""`` statt ``None``: auch ein Lesen ohne Text ist ein Lesen (``docs.unread``).
        doc.text, doc.keywords, doc.facts = p.text, p.keywords or None, p.facts or None
    db.flush()
    return detail(db, doc)


@router.post("/{object_id}/refs", response_model=DocumentDetail)
def add_ref(object_id: int, data: RefIn, db: Session = DB,
            user: UserProfile = Depends(require_employee)):
    """Ein Dokument an einen weiteren Datensatz hängen (Referenz setzen)."""
    doc = docs.readable(db, object_id, user)
    docs.attach(db, doc, data.object_id, user)
    db.flush()
    return detail(db, doc)


@router.delete("/{object_id}/refs/{ref_id}", response_model=DocumentDetail)
def remove_ref(object_id: int, ref_id: int, db: Session = DB,
               user: UserProfile = Depends(require_employee)):
    """Ein Dokument von einem Datensatz lösen (Referenz entfernen) – ein Pflichtfeld nie."""
    doc = docs.readable(db, object_id, user)
    docs.detach(db, doc, ref_id, user)
    db.flush()
    return detail(db, doc)


@router.post("/{object_id}/delete", response_model=DocumentDetail)
def delete_document(object_id: int, data: DeleteIn, db: Session = DB,
                    user: UserProfile = Depends(require_employee)):
    """Ein Dokument löschen, mit Grund – nur, was nirgends mehr hängt."""
    doc = docs.readable(db, object_id, user)
    docs.delete(db, doc, data.reason, user)
    db.flush()
    return detail(db, doc)


# Zuletzt: «/{object_id}» fängt sonst «/requirements» ab.
@router.get("/{object_id}", response_model=DocumentDetail)
def get_document(object_id: int, db: Session = DB,
                 user: UserProfile = Depends(require_employee)):
    """Ein Dokument lesen – **wer welches Dokument geöffnet hat, steht im Log**
    (``document.read``)."""
    doc = docs.readable(db, object_id, user)
    out = detail(db, doc)
    log.event(db, "document.read", doc.object_id)
    db.flush()
    return out
