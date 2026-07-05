"""Geschäftslogik für das Prozessschrittmodul «Dokument».

Der Inhalt wird auf der **Vorlage** (``ArticleProcessStep.document_content``) verfasst,
solange der Artikel im Entwurf ist. Bei der **Auftragsfreigabe** friert
``instantiate_for_order`` je Dokument-Schritt einen unveränderlichen Snapshot in ein
nummeriertes ``Document`` ein (analog ``sale.instantiate_for_order``). Ab dann ist das
Dokument fest – eine Änderung erzeugt eine neue Version, das Original bleibt erhalten.

Der Schritt ist **NEUTRAL** (keine Bestandswirkung) und **PRODUCE** (bringt einen neuen,
nicht-physischen Liefergegenstand hervor) – ein Dokument-Auftrag greift NIE FIFO auf Lager
zu und blockiert nie an Bestands-Unterdeckung.
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Article, Document, Order, UserProfile
from ..models.base import utcnow
from ..schemas.document import DocumentContent
from . import process
from .admin import log_audit
from .events import emit
from .objects import next_object_id


def normalize_content(raw: Optional[dict]) -> dict:
    """Rohinhalt in die kanonische Struktur bringen (leere/fehlende Felder tolerant).

    Nutzt das Pydantic-Schema als Normalisierer – so ist ein gespeicherter Snapshot
    immer wohlgeformt (Titel/Untertitel/Datum + Abschnittsliste)."""
    try:
        return DocumentContent.model_validate(raw or {}).model_dump()
    except Exception:
        return DocumentContent().model_dump()


def instantiate_for_order(db: Session, order: Order, actor_id: int | None) -> list[Document]:
    """Bei Auftragsfreigabe je Dokument-Schritt ein nummeriertes Dokument einfrieren.

    Idempotent: existiert für einen Schritt bereits ein Dokument, wird es übersprungen.
    Committet NICHT – der Aufrufer (Freigabe) schliesst die Transaktion ab."""
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
        content = normalize_content(step.document_content)
        doc = Document(
            object_id=next_object_id(db, "document"),
            order_id=order.id,
            step_id=step.id,
            article_id=order.article_id,
            content=content,
            # ``title`` ist nur die denormalisierte Kurzform (Spalte ``String(255)``);
            # der volle Titel lebt im ``content``-Snapshot. Kappen, damit ein langer Titel
            # die Freigabe-Transaktion nicht mit einem DB-Fehler abbricht.
            title=((content.get("title") or "")[:255] or None),
            version=1,
            created_by=actor_id,
            issued_at=utcnow(),
        )
        db.add(doc)
        db.flush()
        log_audit(db, "documents", None, "Dokument ausgestellt", actor_id, object_id=doc.object_id)
        emit(db, "document.issued", object_type="document", object_id=doc.object_id,
             payload={"order": order.object_id, "title": doc.title}, actor_id=actor_id)
        created.append(doc)
    return created


def get_by_object_id(db: Session, object_id: int) -> Document:
    """Ein eingefrorenes Dokument anhand seiner Objektnummer laden (404, wenn keins)."""
    doc = db.query(Document).filter(
        Document.object_id == object_id, Document.is_active == True).first()
    if not doc:
        raise HTTPException(404, detail="Dokument nicht gefunden")
    return doc


def creator_name(db: Session, doc: Document) -> Optional[str]:
    if not doc.created_by:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == doc.created_by).first()
    return u.display_name if u else None


def order_object_id(db: Session, doc: Document) -> Optional[int]:
    o = db.query(Order.object_id).filter(Order.id == doc.order_id).first()
    return o[0] if o else None


def article_object_id(db: Session, doc: Document) -> Optional[int]:
    if not doc.article_id:
        return None
    a = db.query(Article.object_id).filter(Article.id == doc.article_id).first()
    return a[0] if a else None
