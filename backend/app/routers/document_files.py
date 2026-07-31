"""Hochgeladene Dokumente (Belege/Anleitungen/Rechnungen) – KI-Aufnahme + Reiter «Dokumente».

Drei Bereiche:
* **Aufnahme** (``/api/v1/ai/documents/*``): Datei hochladen → KI analysiert & schlägt Name +
  Objektzuordnung vor (``AiAction``) → Mensch bestätigt/ändert → ablegen (``services/ai/documents``).
* **Anzeige** (``/api/v1/erp/objects/{id}/documents``): der Reiter «Dokumente» je Objekt –
  vereint hochgeladene Dateien (n:m) UND die im Schritt «Dokument» erzeugten Dokumente.
* **Datei** (``/api/v1/erp/document-files/{id}/download|DELETE``): authentifizierter Stream
  (Rechnungen sind sensibel – NICHT der öffentliche Foto-Token-Weg) + Soft-Delete.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import (
    AiAction, Document, DocumentFile, DocumentLink, Instance, Order, UserProfile,
)
from ..schemas.document_file import (
    DocumentAnalyzeResponse, DocumentConfirmRequest, ObjectDocument,
)
from ..services import document as document_svc
from ..services import people
from ..services import storage
from ..services.ai import actions as actions_svc
from ..services.ai import documents as ai_documents
from ..services.ai.identity import ensure_ai_user
from ..services.ai.principal import AiPrincipal
from ..services.events import emit
from ..services.objects import resolve_object_type

router = APIRouter(tags=["documents"])


def _principal(db: Session, user: UserProfile) -> AiPrincipal:
    return AiPrincipal(actor=ensure_ai_user(db), on_behalf_of=user)


# ─── Aufnahme: analysieren → bestätigen/ablehnen ──────────────────────────────────

@router.post("/api/v1/ai/documents/analyze", response_model=DocumentAnalyzeResponse)
async def analyze_document(
    file: UploadFile = File(...),
    context_object_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Ein Dokument hochladen; die KI liest es und schlägt Name + Objektzuordnung vor.
    Ergebnis ist ein **Vorschlag** – erst ``confirm`` legt das Dokument an."""
    raw = await file.read()
    mime = (file.content_type or "application/octet-stream").split(";")[0].strip()
    result = ai_documents.analyze(db, _principal(db, user), raw, file.filename, mime, context_object_id)
    return DocumentAnalyzeResponse(**result)


@router.post("/api/v1/ai/documents/{action_id}/confirm", response_model=ObjectDocument)
async def confirm_document(
    action_id: int,
    body: DocumentConfirmRequest,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Menschliche Bestätigung: Name + Objektzuordnung festschreiben → Dokument anlegen
    (über den autorisierten ``AiAction``-Pfad). Zuordnung ist Pflicht (min. ein Objekt)."""
    action = db.query(AiAction).filter(AiAction.id == action_id, AiAction.is_active == True).first()
    if not action or action.action_type != "link_document":
        raise HTTPException(404, detail="Dokument-Vorschlag nicht gefunden")
    if action.status != "proposed":
        raise HTTPException(409, detail=f"Vorschlag ist bereits '{action.status}'")

    links: list[dict] = []
    seen: set[int] = set()
    for i, link in enumerate(body.links):
        t = resolve_object_type(db, link.object_id)
        if not t:
            raise HTTPException(400, detail=f"Objektnummer {link.object_id} existiert nicht")
        if link.object_id in seen:
            continue
        seen.add(link.object_id)
        links.append({"object_id": link.object_id, "object_type": t,
                      "relation": link.relation or "about",
                      "primary": bool(link.primary) or i == 0})
    if not any(l["primary"] for l in links):
        links[0]["primary"] = True

    # Finalen Stand in der Aktion persistieren, DANN über den Standard-Confirm ausführen
    # (er liest die Aktion frisch – reassign statt In-Place-Mutation, damit JSONB dirty wird).
    storage_key = (action.payload or {}).get("storage_key")
    action.payload = {**(action.payload or {}),
                      "final_title": body.title.strip(),
                      "final_doc_type": body.doc_type, "links": links}
    db.commit()

    actions_svc.confirm(db, action_id, user)   # → materialize (idempotent, autorisiert)

    df = db.query(DocumentFile).filter(DocumentFile.storage_key == storage_key,
                                       DocumentFile.is_active == True).first()
    if not df:
        raise HTTPException(500, detail="Dokument konnte nicht angelegt werden")
    primary_rel = next((l["relation"] for l in links if l["primary"]), "about")
    return _file_entry(db, df, primary_rel)


@router.post("/api/v1/ai/documents/{action_id}/reject")
async def reject_document(
    action_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Vorschlag ablehnen: die (noch nicht zugeordnete) Datei wird aus der Ablage entfernt."""
    action = db.query(AiAction).filter(AiAction.id == action_id, AiAction.is_active == True).first()
    if not action or action.action_type != "link_document":
        raise HTTPException(404, detail="Dokument-Vorschlag nicht gefunden")
    p = action.payload or {}
    if action.status == "proposed" and p.get("storage_key"):
        storage.delete(db, p["storage_key"], p.get("storage_backend") or "db")
    actions_svc.reject(db, action_id, user)
    return {"rejected": True}


# ─── Reiter «Dokumente» je Objekt (hochgeladene + erzeugte) ────────────────────────

@router.get("/api/v1/erp/objects/{object_id}/documents", response_model=list[ObjectDocument])
async def object_documents(
    object_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Alle Dokumente eines Objekts: hochgeladene Dateien (n:m) + im Schritt «Dokument»
    erzeugte Dokumente. Neueste zuerst."""
    out: list[ObjectDocument] = []

    links = (db.query(DocumentLink)
             .filter(DocumentLink.object_id == object_id, DocumentLink.is_active == True)
             .all())
    rel_by_doc = {l.document_id: l.relation for l in links}
    doc_ids = list(rel_by_doc.keys())
    if doc_ids:
        files = (db.query(DocumentFile)
                 .filter(DocumentFile.id.in_(doc_ids), DocumentFile.is_active == True)
                 .all())
        for df in files:
            out.append(_file_entry(db, df, rel_by_doc.get(df.id)))

    out.extend(_generated_for(db, object_id))

    out.sort(key=lambda d: d.created_at.timestamp() if d.created_at else 0.0, reverse=True)
    return out


@router.get("/api/v1/erp/document-files/{doc_id}/download")
async def download_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Die Datei authentifiziert ausliefern (inline – Vorschau im Browser)."""
    df = db.query(DocumentFile).filter(DocumentFile.id == doc_id, DocumentFile.is_active == True).first()
    if not df:
        raise HTTPException(404, detail="Dokument nicht gefunden")
    data, mime = storage.read(db, df.storage_key, df.storage_backend)
    fname = df.filename or f"{df.title[:60]}"
    return Response(
        content=data, media_type=df.mime or mime,
        headers={"Content-Disposition": f'inline; filename="{_ascii(fname)}"',
                 "Cache-Control": "private, max-age=3600"},
    )


@router.delete("/api/v1/erp/document-files/{doc_id}")
async def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: UserProfile = Depends(require_employee),
):
    """Dokument entfernen (Soft-Delete – die Datei bleibt archiviert, verschwindet aber
    aus den Reitern). Verknüpfungen werden mit deaktiviert."""
    df = db.query(DocumentFile).filter(DocumentFile.id == doc_id, DocumentFile.is_active == True).first()
    if not df:
        raise HTTPException(404, detail="Dokument nicht gefunden")
    df.is_active = False
    db.query(DocumentLink).filter(DocumentLink.document_id == df.id).update(
        {DocumentLink.is_active: False})
    emit(db, "document.removed", object_type="document", object_id=df.object_id,
         payload={"title": df.title, "by": user.id}, actor_id=user.id)
    db.commit()
    return {"deleted": True}


# ─── Helfer ───────────────────────────────────────────────────────────────────────

def _ascii(s: str) -> str:
    # Für den Content-Disposition-Header: nur druckbares ASCII, ohne Zeichen, die den
    # Header-Wert brechen/verwirren könnten (Anführungszeichen/Backslash). Steuerzeichen
    # (inkl. CR/LF → Header-Splitting) fallen bereits durch die Bereichsprüfung weg.
    cleaned = "".join(c for c in s if 32 <= ord(c) < 127 and c not in '"\\')
    return cleaned.strip() or "dokument"


def _file_entry(db: Session, df: DocumentFile, relation: Optional[str]) -> ObjectDocument:
    return ObjectDocument(
        kind="file", id=df.id, object_number=df.object_id, title=df.title,
        doc_type=df.doc_type, summary=df.summary, mime=df.mime, filename=df.filename,
        page_count=df.page_count, byte_size=df.byte_size,
        download_url=f"/api/v1/erp/document-files/{df.id}/download",
        relation=relation, created_at=df.created_at, created_by_name=people.name_by_id(db, df.created_by),
    )


def _gen_entry(db: Session, doc: Document, instance: Optional[Instance]) -> ObjectDocument:
    """Ein erstelltes Dokument als Reiter-Eintrag. Es IST die vom Auftrag erzeugte Instanz –
    daher trägt es deren Status (nicht «Erstellt») und seinen Inhalt (für die Inline-Vorschau
    ohne PDF-Iframe)."""
    content = doc.content or {}
    title = (content.get("title") or "").strip() or "Dokument"
    return ObjectDocument(
        kind="generated", id=doc.id,
        object_number=instance.object_id if instance else None, title=title,
        doc_type="generated", summary=(content.get("subtitle") or None),
        mime="application/pdf", filename=None, page_count=None, byte_size=None,
        download_url=f"/api/v1/erp/documents/{doc.id}/pdf",
        relation="issued",
        created_at=(instance.released_at if instance else None) or doc.created_at,
        created_by_name=document_svc.creator_name(db, doc),
        content=content,
        quality=(instance.quality if instance else None),
        disposition=(instance.disposition if instance else None),
        reserved=bool(instance and (instance.reserved_quantity or 0) > 0),
        signoffs=document_svc.signoff_views(db, doc),
    )


def _generated_for(db: Session, object_id: int) -> list[ObjectDocument]:
    """Im Prozessschritt «Dokument» erzeugte, ausgestellte Dokumente mit Bezug zu diesem Objekt.

    Das Dokument = die vom Auftrag erzeugte Instanz. Wir reichen die Instanz durch, damit der
    Eintrag deren Status trägt (Kernpunkt: Dokument-Status == Instanz-Status)."""
    t = resolve_object_type(db, object_id)
    out: list[ObjectDocument] = []

    def _docs_of(order: Order):
        return (db.query(Document)
                .filter(Document.order_id == order.id, Document.done == True,
                        Document.is_active == True).order_by(Document.id).all())

    if t == "instance":
        inst = db.query(Instance).filter(Instance.object_id == object_id,
                                         Instance.is_active == True).first()
        if inst:
            order = db.query(Order).filter(Order.id == inst.order_id).first() if inst.order_id else None
            owner = document_svc.produced_instance(db, order) if order else None
            if owner is not None and owner.object_id == inst.object_id:
                for d in _docs_of(order):
                    out.append(_gen_entry(db, d, inst))
        return out
    if t == "order":
        o = db.query(Order).filter(Order.object_id == object_id).first()
        if o:
            inst = document_svc.produced_instance(db, o)
            for d in _docs_of(o):
                out.append(_gen_entry(db, d, inst))
        return out
    if t == "article":
        from ..models import Article
        a = db.query(Article).filter(Article.object_id == object_id).first()
        if a:
            docs = (db.query(Document)
                    .filter(Document.article_id == a.id, Document.done == True,
                            Document.is_active == True).order_by(Document.id.desc()).all())
            for d in docs:
                order = db.query(Order).filter(Order.id == d.order_id).first()
                inst = document_svc.produced_instance(db, order) if order else None
                out.append(_gen_entry(db, d, inst))
        return out
    return out
