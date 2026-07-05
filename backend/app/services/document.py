"""Geschäftslogik für das Prozessschrittmodul «Dokument».

Der Inhalt wird **während der Auftragsausführung** an diesem Schritt verfasst (analog zur
Datenerfassung ``Inspection``) und mit «Ausstellen» (``done``) festgeschrieben. Das Dokument
trägt KEINE eigene Objektnummer: seine Nummer ist die **Instanz-Objektnummer**, sein Datum das
**Freigabedatum der Instanz** (``instances.released_at``). Verschiedene Ausfertigungen =
verschiedene Aufträge/Instanzen (kein Versionsfeld).

Der Schritt ist **NEUTRAL** (keine Bestandswirkung) und **PRODUCE**: der Auftrag erzeugt – wie
jeder Erzeugungsauftrag – eine Instanz (den Liefergegenstand), an die das Dokument gebunden ist.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Document, Instance, Order, UserProfile
from ..schemas.document import DocumentContent, DocumentUpdate
from . import process
from .admin import log_audit
from .events import emit


def normalize_content(raw: Optional[dict]) -> dict:
    """Rohinhalt in die kanonische Struktur bringen (leere/fehlende Felder tolerant)."""
    try:
        return DocumentContent.model_validate(raw or {}).model_dump()
    except Exception:
        return DocumentContent().model_dump()


def instantiate_for_order(db: Session, order: Order, actor_id: int | None) -> list[Document]:
    """Bei Auftragsfreigabe je Dokument-Schritt eine LEERE, noch offene Fachzeile anlegen.

    Der Inhalt wird erst während der Ausführung verfasst (``record_document``). Idempotent:
    existiert für einen Schritt bereits ein Dokument, wird es übersprungen. Committet NICHT."""
    steps = [d for d in process.order_step_defs(db, order) if d.step_type == "document"]
    if not steps:
        return []
    have_step_ids = {
        d.step_id for d in db.query(Document)
        .filter(Document.order_id == order.id, Document.is_active == True).all()
    }
    created: list[Document] = []
    for step in steps:
        if step.id in have_step_ids:
            continue   # idempotent
        doc = Document(
            order_id=order.id, step_id=step.id, article_id=order.article_id,
            content=normalize_content(None), done=False, created_by=actor_id,
        )
        db.add(doc)
        db.flush()
        created.append(doc)
    return created


def record_document(db: Session, order: Order, data: DocumentUpdate, actor_id: int | None) -> Order:
    """Inhalt des Dokument-Schritts verfassen/ausstellen (analog ``inspection.record_inspection``).

    ``action='save'`` → Zwischenstand; ``action='issue'`` → ausgestellt (Schritt erledigt,
    Inhalt festgeschrieben). Committet und bewertet den Auftragsabschluss neu."""
    step = process.resolve_exec_step(db, order, "document", data.step_id)
    doc = (
        db.query(Document)
        .filter(Document.order_id == order.id, Document.step_id == step.id,
                Document.is_active == True).first()
    )
    if doc is None:
        doc = Document(order_id=order.id, step_id=step.id, article_id=order.article_id)
        db.add(doc)
    if doc.done:
        raise HTTPException(409, detail="Dokument ist bereits ausgestellt und unveränderlich")
    doc.content = normalize_content(data.content.model_dump())
    doc.created_by = actor_id
    if data.action == "issue":
        doc.done = True
        db.flush()
        log_audit(db, "documents", "document", "Dokument ausgestellt", actor_id, object_id=order.object_id)
        emit(db, "document.issued", object_type="order", object_id=order.object_id,
             payload={"title": (doc.content or {}).get("title")}, actor_id=actor_id)
    db.commit()
    process.recompute_completion(db, order)
    db.commit()
    return order


def produced_instance(db: Session, order: Order) -> Optional[Instance]:
    """Die vom Auftrag erzeugte Instanz (Liefergegenstand des Dokuments) – kleinste Nummer.

    Ihre Objektnummer IST die Dokumentennummer, ihr ``released_at`` das Dokumentdatum."""
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .first()
    )


def get_by_id(db: Session, doc_id: int) -> Document:
    """Ein Dokument (Fachzeile) anhand seiner id laden (404, wenn keins)."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.is_active == True).first()
    if not doc:
        raise HTTPException(404, detail="Dokument nicht gefunden")
    return doc


def creator_name(db: Session, doc: Document) -> Optional[str]:
    if not doc.created_by:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == doc.created_by).first()
    return u.display_name if u else None


def render_meta(db: Session, order: Order) -> tuple[Optional[int], Optional[datetime]]:
    """Nummer (= Instanz-Objektnummer) und Datum (= Instanz-Freigabe) für die PDF-Ausgabe."""
    inst = produced_instance(db, order)
    if inst is None:
        return None, None
    return inst.object_id, inst.released_at


def instance_document_embeds(db: Session, instance: Instance) -> list:
    """Ausgestellte Dokumente, deren Nummer GENAU diese Instanz ist (der Liefergegenstand).

    Bindeglied Instanz→Dokument: das Dokument gehört zum Auftrag der Instanz und dessen
    ``produced_instance`` IST diese Instanz (die kleinste Objektnummer des Auftrags trägt die
    Dokumentennummer). So erscheint ein Dokument nur an «seiner» Instanz. Ergibt den
    ``DocumentEmbed`` (Inhalt + Nummer = Instanz-Objektnummer + Datum = Instanz-Freigabe).
    Auch der Andockpunkt für die spätere KI-/Scan-Ablage (beliebige PDFs je Objektnummer)."""
    from ..schemas.document import DocumentEmbed
    if instance.order_id is None:
        return []
    order = db.query(Order).filter(Order.id == instance.order_id).first()
    if order is None:
        return []
    owner = produced_instance(db, order)
    if owner is None or owner.object_id != instance.object_id:
        return []
    docs = (
        db.query(Document)
        .filter(Document.order_id == order.id, Document.done == True, Document.is_active == True)
        .order_by(Document.id)
        .all()
    )
    out = []
    for doc in docs:
        emb = DocumentEmbed.model_validate(doc)
        emb.created_by_name = creator_name(db, doc)
        emb.object_number = instance.object_id
        emb.document_date = instance.released_at
        out.append(emb)
    return out
