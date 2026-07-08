"""Geschäftslogik für das Prozessschrittmodul «Dokument».

Der Inhalt wird **während der Auftragsausführung** an diesem Schritt verfasst (analog zur
Datenerfassung ``Inspection``) und mit «Ausstellen» (``done``) festgeschrieben. Das Dokument
trägt KEINE eigene Objektnummer: seine Nummer ist die **Instanz-Objektnummer**, sein Datum das
**Freigabedatum der Instanz** (``instances.released_at``). Verschiedene Ausfertigungen =
verschiedene Aufträge/Instanzen (kein Versionsfeld).

Der Schritt ist **NEUTRAL** (keine Bestandswirkung) und **PRODUCE**: der Auftrag erzeugt – wie
jeder Erzeugungsauftrag – eine Instanz (den Liefergegenstand), an die das Dokument gebunden ist.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    ArticleProcessStep, Document, DocumentSignoff, Instance, Order, UserProfile,
)
from ..schemas.document import DocumentContent, DocumentUpdate, SignoffView
from . import process
from .admin import log_audit
from .events import emit

_STAFF_ROLES = ("admin", "employee")


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

    ``action='save'`` → Zwischenstand; ``action='issue'`` → **ausgestellt**: der Inhalt wird
    festgeschrieben (``issued``) und die Freigabe-Parteien (``doc_signers`` am Schritt) werden
    als offene Signoffs erzeugt. Sind **keine** Parteien deklariert, ist das Dokument sofort
    **freigegeben** (``done``, rückwärtskompatibel) – sonst erst, wenn ALLE signiert haben
    (siehe ``act_on_signoff``). Committet und bewertet den Auftragsabschluss neu."""
    step = process.resolve_exec_step(db, order, "document", data.step_id)
    doc = (
        db.query(Document)
        .filter(Document.order_id == order.id, Document.step_id == step.id,
                Document.is_active == True).first()
    )
    if doc is None:
        doc = Document(order_id=order.id, step_id=step.id, article_id=order.article_id)
        db.add(doc)
    if doc.issued:
        raise HTTPException(409, detail="Dokument ist bereits ausgestellt und unveränderlich")
    doc.content = normalize_content(data.content.model_dump())
    doc.created_by = actor_id
    if data.action == "issue":
        doc.issued = True
        db.flush()
        _create_signoffs(db, order, doc, step)
        log_audit(db, "documents", "document", "Dokument ausgestellt", actor_id, object_id=order.object_id)
        emit(db, "document.issued", object_type="order", object_id=order.object_id,
             payload={"title": (doc.content or {}).get("title")}, actor_id=actor_id)
        _maybe_complete(db, order, doc)   # ohne Parteien: sofort freigeben
    db.commit()
    process.recompute_completion(db, order)
    db.commit()
    return order


# ─── Freigabe-Parteien (Unterschriften-/Bestätigungs-Layer) ──────────────────────

def _create_signoffs(db: Session, order: Order, doc: Document, step: ArticleProcessStep) -> None:
    """Beim Ausstellen die deklarierten Freigabe-Parteien (``step.doc_signers``) als offene
    Signoffs materialisieren (idempotent: existieren schon welche, nichts tun)."""
    have = db.query(DocumentSignoff.id).filter(
        DocumentSignoff.document_id == doc.id, DocumentSignoff.is_active == True).first()
    if have:
        return
    for idx, entry in enumerate(step.doc_signers or []):
        try:
            signer_obj = int(entry.get("signer_object_id"))
        except (TypeError, ValueError, AttributeError):
            continue
        action = entry.get("action") if entry.get("action") in ("confirm", "sign") else "sign"
        db.add(DocumentSignoff(
            document_id=doc.id, order_id=order.id, signer_object_id=signer_obj,
            action=action, order_index=idx, status="pending",
        ))
    db.flush()


def get_signoff(db: Session, signoff_id: int) -> DocumentSignoff:
    so = db.query(DocumentSignoff).filter(
        DocumentSignoff.id == signoff_id, DocumentSignoff.is_active == True).first()
    if not so:
        raise HTTPException(404, detail="Freigabe-Partei nicht gefunden")
    return so


def signoffs_for(db: Session, doc: Document) -> list[DocumentSignoff]:
    return (
        db.query(DocumentSignoff)
        .filter(DocumentSignoff.document_id == doc.id, DocumentSignoff.is_active == True)
        .order_by(DocumentSignoff.order_index, DocumentSignoff.id)
        .all()
    )


def signoffs_complete(rows: list[DocumentSignoff]) -> bool:
    """Alle Freigabe-Parteien signiert? Ohne Parteien → True (rückwärtskompatibel)."""
    return all(r.status == "signed" for r in rows)


def _maybe_complete(db: Session, order: Order, doc: Document) -> None:
    """Ist der Inhalt ausgestellt UND haben alle Parteien signiert, das Dokument
    **freigeben** (``done``) – erst das schliesst den Prozessschritt ab."""
    if not doc.issued or doc.done:
        return
    if signoffs_complete(signoffs_for(db, doc)):
        doc.done = True
        db.flush()
        emit(db, "document.released", object_type="order", object_id=order.object_id,
             payload={"document_id": doc.id}, actor_id=None)


def _signoff_step(db: Session, doc: Document) -> Optional[ArticleProcessStep]:
    if doc.step_id is None:
        return None
    return db.query(ArticleProcessStep).filter(ArticleProcessStep.id == doc.step_id).first()


def _assert_actionable(db: Session, doc: Document, signoff: DocumentSignoff) -> None:
    """Sequenzielles Signieren erzwingen: ist die Reihenfolge gefordert, darf nur die
    Partei mit dem kleinsten ``order_index`` unter den noch offenen (pending) handeln."""
    step = _signoff_step(db, doc)
    if not step or not getattr(step, "sign_sequential", False):
        return
    pending = [r for r in signoffs_for(db, doc) if r.status == "pending"]
    if pending and signoff.id != min(pending, key=lambda r: (r.order_index, r.id)).id:
        raise HTTPException(409, detail="Eine andere Partei muss zuerst unterschreiben (Reihenfolge)")


def act_on_signoff(db: Session, signoff: DocumentSignoff, data, user: UserProfile) -> Order:
    """Eine Freigabe-Partei handelt auf «ihr» Signoff: ``confirm``/``sign`` (signieren),
    ``reject`` (ablehnen, mit Grund) oder ``withdraw`` (eigene Unterschrift zurückziehen).

    Berechtigt ist ausschliesslich die **benannte Person** (Objektnummer-Abgleich) – so
    signiert jede Partei selbst (Nachvollziehbarkeit). Committet und bewertet den Abschluss neu.
    """
    doc = db.query(Document).filter(
        Document.id == signoff.document_id, Document.is_active == True).first()
    if not doc:
        raise HTTPException(404, detail="Dokument nicht gefunden")
    order = db.query(Order).filter(Order.id == signoff.order_id).first()
    if not order:
        raise HTTPException(404, detail="Auftrag nicht gefunden")
    if user.object_id != signoff.signer_object_id:
        raise HTTPException(403, detail="Nur die benannte Person darf hier unterschreiben")
    if doc.done:
        raise HTTPException(409, detail="Dokument ist bereits vollständig freigegeben")

    action = data.action
    if action == "withdraw":
        signoff.status = "pending"
        signoff.signature_url = None
        signoff.reason = None
        signoff.acted_at = None
        verb = "Unterschrift zurückgezogen"
    elif action == "reject":
        _assert_actionable(db, doc, signoff)
        signoff.status = "rejected"
        signoff.reason = (data.reason or "").strip() or None
        signoff.acted_at = datetime.now(timezone.utc)
        signoff.acted_by = user.id
        verb = "Freigabe abgelehnt"
    else:  # confirm | sign
        _assert_actionable(db, doc, signoff)
        if signoff.action == "sign" and not (data.signature_url or "").strip():
            raise HTTPException(400, detail="Für diese Partei ist eine Unterschrift erforderlich")
        signoff.status = "signed"
        signoff.signature_url = (data.signature_url or None) if signoff.action == "sign" else None
        signoff.reason = None
        signoff.acted_at = datetime.now(timezone.utc)
        signoff.acted_by = user.id
        verb = "unterschrieben" if signoff.action == "sign" else "bestätigt"

    db.flush()
    log_audit(db, "document_signoffs", "status", signoff.status, user.id, object_id=order.object_id)
    emit(db, f"document.signoff.{signoff.status}", object_type="order", object_id=order.object_id,
         payload={"signer": user.object_id, "verb": verb}, actor_id=user.id)
    _maybe_complete(db, order, doc)
    db.commit()
    process.recompute_completion(db, order)
    db.commit()
    return order


def withdraw_issuance(db: Session, order: Order, step_id: int | None, user: UserProfile) -> Order:
    """Die Ausstellung **zurücknehmen** (Personal): der Inhalt wird wieder editierbar, alle
    Signoffs verworfen. Nur solange das Dokument noch nicht vollständig freigegeben ist –
    ein freigegebenes Dokument (Instanz released) bleibt unveränderlich."""
    step = process.resolve_exec_step(db, order, "document", step_id)
    doc = (
        db.query(Document)
        .filter(Document.order_id == order.id, Document.step_id == step.id,
                Document.is_active == True).first()
    )
    if not doc or not doc.issued:
        raise HTTPException(409, detail="Dieses Dokument ist nicht ausgestellt")
    if doc.done:
        raise HTTPException(409, detail="Ein vollständig freigegebenes Dokument kann nicht zurückgenommen werden")
    for row in signoffs_for(db, doc):
        row.is_active = False
    doc.issued = False
    db.flush()
    log_audit(db, "documents", "document", "Ausstellung zurückgenommen", user.id, object_id=order.object_id)
    emit(db, "document.withdrawn", object_type="order", object_id=order.object_id, actor_id=user.id)
    db.commit()
    return order


def _user_name(db: Session, object_id: int) -> Optional[str]:
    u = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
    return u.display_name if u else None


def signoff_views(db: Session, doc: Document) -> list[SignoffView]:
    """Freigabe-Parteien eines Dokuments als Ansicht (mit Namen) – für den Auftrags-Embed."""
    out: list[SignoffView] = []
    for r in signoffs_for(db, doc):
        v = SignoffView.model_validate(r)
        v.signer_name = _user_name(db, r.signer_object_id)
        out.append(v)
    return out


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
        _enrich_embed(db, doc, emb)
        out.append(emb)
    return out


def _enrich_embed(db: Session, doc: Document, emb) -> None:
    """Freigabe-Parteien + Schritt-Deklaration (Sichtbarkeit/Reihenfolge) in den Embed ziehen."""
    emb.signoffs = signoff_views(db, doc)
    step = _signoff_step(db, doc)
    if step is not None:
        emb.sign_sequential = bool(getattr(step, "sign_sequential", False))
        emb.visibility = getattr(step, "doc_visibility", None) or "internal"


def my_pending_signoffs(db: Session, user: UserProfile) -> list[dict]:
    """Dokumente, auf die **ich** als Freigabe-Partei noch handeln muss (offen/abgelehnt) –
    für «Meine Dokumente». Nur ausgestellte, noch nicht vollständig freigegebene Dokumente.

    Bei sequenzieller Reihenfolge wird ``actionable`` markiert, ob ich JETZT an der Reihe bin."""
    rows = (
        db.query(DocumentSignoff)
        .filter(DocumentSignoff.signer_object_id == user.object_id,
                DocumentSignoff.is_active == True,
                DocumentSignoff.status.in_(("pending", "rejected")))
        .order_by(DocumentSignoff.id.desc())
        .all()
    )
    out: list[dict] = []
    for so in rows:
        doc = db.query(Document).filter(
            Document.id == so.document_id, Document.is_active == True,
            Document.issued == True, Document.done == False).first()
        if not doc:
            continue
        order = db.query(Order).filter(Order.id == so.order_id).first()
        obj_nr, doc_date = render_meta(db, order) if order else (None, None)
        step = _signoff_step(db, doc)
        actionable = True
        if step is not None and getattr(step, "sign_sequential", False):
            pending = [r for r in signoffs_for(db, doc) if r.status == "pending"]
            actionable = bool(pending) and so.id == min(pending, key=lambda r: (r.order_index, r.id)).id
        out.append({
            "signoff_id": so.id,
            "object_number": obj_nr,
            "document_date": doc_date,
            "action": so.action,
            "status": so.status,
            "actionable": actionable,
            "content": doc.content,
            "title": (doc.content or {}).get("title") or "Dokument",
        })
    return out
