"""Consent-Gate: versionierte Bestätigung von Pflichtdokumenten (AGB/Datenschutz/…).

Ein Pflichtdokument ist versioniert – seine „Version" ist die **Objektnummer der aktuell
gültigen Dokument-Instanz** (aufgelöst über ``services/legal.resolve``, das der Artikel-/
``replaced_by_id``-Kette folgt). Welche Arten von WEM bestätigt werden müssen, steht am
Unternehmen (``company_settings.legal_ack_config`` = ``{kind: [Rollen]}``, ``"all"`` = jede
Rolle). Wer welche Version wann bestätigt hat, liegt in ``document_acknowledgements``.

Ein Nutzer hat für eine ``kind`` **offenen Bedarf**, wenn (a) seine Rolle im Geltungsbereich
liegt, (b) ein gültiges Dokument auflösbar ist und (c) er die **aktuelle** Version noch nicht
bestätigt hat. Wird eine neue Fassung veröffentlicht (neue Instanz-Objektnummer), entsteht der
Bedarf automatisch neu – ohne Sonderlogik.
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Article, ArticleProcessStep, Document, DocumentAcknowledgement, Order, UserProfile,
)
from . import legal
from .admin import get_or_create_settings, log_audit
from .events import emit

# Sonder-„kind" für ein offenes Anerkennungs-Dokument (kein Rechtsdokument-Zeiger, sondern
# ein released Dokument mit deklariertem Publikum). Version = seine Instanz-Objektnummer.
AUDIENCE_KIND = "document"

_KIND_LABELS = {
    "agb": "AGB", "datenschutz": "Datenschutzerklärung", "impressum": "Impressum",
    "widerruf": "Widerrufsbelehrung", "supplier_terms": "Lieferantenvereinbarung",
}

# Welche Dokument-Arten IMMER aktiv bestätigt werden müssen (rechtlich klar «zu akzeptieren»)
# – hart verdrahtet statt konfigurierbar (kein Admin-Häkchen). Gilt für ALLE angemeldeten
# Rollen. Eine Art wird nur dann verlangt, wenn am Unternehmen auch tatsächlich ein Dokument
# dafür hinterlegt/auflösbar ist (sonst gibt es nichts zu bestätigen).
MUST_ACKNOWLEDGE_KINDS: tuple[str, ...] = ("agb",)


def _label(kind: str, content: dict | None) -> str:
    if content and content.get("title"):
        return content["title"]
    return _KIND_LABELS.get(kind, kind.replace("_", " ").upper())


def _config(settings) -> dict:
    return settings.legal_ack_config or {}


def _role_in_scope(role: str | None, roles) -> bool:
    return bool(roles) and ("all" in roles or (role is not None and role in roles))


def required_kinds(settings, role: str | None) -> list[str]:
    """Die Dokument-Arten, die bestätigt werden müssen – **hart verdrahtet** (``MUST_ACKNOWLEDGE_
    KINDS``), für **jede** Rolle gleich. ``settings``/``role`` bleiben in der Signatur (Tests/
    künftige Rollen-Feinsteuerung), werden aktuell aber nicht ausgewertet. Ob tatsächlich etwas
    zu bestätigen ist, entscheidet erst die Auflösung eines gültigen Dokuments (siehe
    ``pending_documents``)."""
    return list(MUST_ACKNOWLEDGE_KINDS)


def _has_ack(db: Session, user_id: int, kind: str, version: int) -> bool:
    return (
        db.query(DocumentAcknowledgement.id)
        .filter(DocumentAcknowledgement.user_id == user_id,
                DocumentAcknowledgement.kind == kind,
                DocumentAcknowledgement.version_object_id == version,
                DocumentAcknowledgement.is_active == True)
        .first() is not None
    )


def _in_audience(user: UserProfile, step: ArticleProcessStep) -> bool:
    """Gehört der Nutzer zum offenen **Anerkennungs-Publikum** dieses Dokument-Schritts?
    'all' → jede angemeldete Rolle · 'roles' → Rolle in der Liste · 'persons' → Objektnummer
    in der Liste. Kein Publikum deklariert → nein."""
    aud = getattr(step, "doc_audience", None)
    if aud == "all":
        return True
    if aud == "roles":
        return bool(user.role and user.role in (step.doc_audience_roles or []))
    if aud == "persons":
        return user.object_id in {int(x) for x in (step.doc_audience_person_ids or [])}
    return False


def _audience_obligations(db: Session, user: UserProfile) -> list[dict]:
    """Offene Anerkennungen des Nutzers aus **released Dokumenten mit Publikum** (nicht die
    Rechtsdokument-Zeiger). Kanonisch: nur die aktuelle Fassung – ein Dokument, dessen Artikel
    **ersetzt** wurde, ist superseded und wird übersprungen (die Nachfolge-Fassung fordert dann
    ihre eigene, neue Anerkennung → Q2 «neue Version = sofort neu bestätigen»)."""
    from .document import produced_instance
    rows = (
        db.query(Document, ArticleProcessStep)
        .join(ArticleProcessStep, Document.step_id == ArticleProcessStep.id)
        .filter(Document.done == True, Document.is_active == True,
                ArticleProcessStep.doc_audience.isnot(None))
        .all()
    )
    out: list[dict] = []
    seen: set[int] = set()
    for doc, step in rows:
        if not _in_audience(user, step):
            continue
        if doc.article_id is not None:
            art = db.query(Article).filter(Article.id == doc.article_id).first()
            if art is not None and art.replaced_by_id is not None:
                continue   # ersetzte Fassung – der Nachfolger fordert die Anerkennung
        order = db.query(Order).filter(Order.id == doc.order_id).first()
        inst = produced_instance(db, order) if order else None
        if inst is None:
            continue
        version = inst.object_id
        if version in seen or _has_ack(db, user.id, AUDIENCE_KIND, version):
            continue
        seen.add(version)
        out.append({
            "kind": AUDIENCE_KIND,
            "title": (doc.content or {}).get("title") or "Dokument",
            "object_number": version,
            "document_date": inst.released_at,
            "content": doc.content,
        })
    return out


def pending_documents(db: Session, user: UserProfile) -> list[dict]:
    """Alle für diesen Nutzer noch offenen Pflicht-Bestätigungen (aktuelle Version, ungeprüft):
    (1) Rechtsdokument-Zeiger (AGB … hart verdrahtet) + (2) released Dokumente mit Publikum."""
    settings = get_or_create_settings(db)
    out: list[dict] = []
    seen: set[int] = set()
    for kind in required_kinds(settings, user.role):
        resolved = legal.resolve(db, kind)
        if not resolved or not resolved.get("object_number"):
            continue   # kein gültiges Dokument hinterlegt → nichts zu bestätigen
        if _has_ack(db, user.id, kind, resolved["object_number"]):
            continue
        seen.add(resolved["object_number"])
        out.append({
            "kind": kind,
            "title": _label(kind, resolved.get("content")),
            "object_number": resolved["object_number"],
            "document_date": resolved.get("document_date"),
            "content": resolved.get("content"),
        })
    # (2) Offene Anerkennungen aus released Dokumenten mit Publikum (dedupe gegen die Zeiger).
    for item in _audience_obligations(db, user):
        if item["object_number"] not in seen:
            seen.add(item["object_number"])
            out.append(item)
    return out


def acknowledge(db: Session, user: UserProfile, kind: str, object_number: int | None = None) -> None:
    """Die **aktuelle** Version von ``kind`` für den Nutzer als bestätigt festhalten
    (idempotent). Committet.

    Zwei Wege: ein **Rechtsdokument-Zeiger** (``kind`` = agb …, Version via ``legal.resolve``)
    ODER ein **Publikums-Dokument** (``kind='document'`` + ``object_number`` der released
    Instanz – muss eine offene Anerkennung des Nutzers sein)."""
    if kind == AUDIENCE_KIND:
        if object_number is None:
            raise HTTPException(400, detail="Objektnummer des Dokuments fehlt")
        version = int(object_number)
        # Nur bestätigen, was tatsächlich offen (im Publikum) ist – oder bereits bestätigt (idempotent).
        legit = any(o["object_number"] == version for o in _audience_obligations(db, user))
        if not legit and not _has_ack(db, user.id, kind, version):
            raise HTTPException(400, detail="Dieses Dokument ist für dich nicht zu bestätigen")
    else:
        settings = get_or_create_settings(db)
        if kind not in required_kinds(settings, user.role):
            raise HTTPException(400, detail="Für dich ist keine Bestätigung dieses Dokuments erforderlich")
        resolved = legal.resolve(db, kind)
        if not resolved or not resolved.get("object_number"):
            raise HTTPException(400, detail="Kein gültiges Dokument hinterlegt")
        version = resolved["object_number"]
    if _has_ack(db, user.id, kind, version):
        return   # schon bestätigt (idempotent)
    now = datetime.now(timezone.utc)
    db.add(DocumentAcknowledgement(
        user_id=user.id, kind=kind, version_object_id=version, accepted_at=now))
    # Rückwärtskompatibel: die AGB-Bestätigung spiegelt weiterhin die Profil-Felder.
    if kind == "agb":
        user.terms_accepted_at = now
        user.terms_version = str(version)
    log_audit(db, "document_acknowledgements", None, f"{kind} (Version {version}) bestätigt",
              user.id, object_id=user.object_id)
    emit(db, "document.acknowledged", object_type="user", object_id=user.object_id,
         payload={"kind": kind, "version": version}, actor_id=user.id)
    db.commit()


def my_document_history(db: Session, user: UserProfile) -> list[dict]:
    """Alle **erledigten** Dokument-Vorgänge des Nutzers – für «Meine Dokumente» (damit ein
    bereits akzeptiertes/unterschriebenes Dokument sichtbar bleibt, nicht nur die offenen):
    (1) eigene Unterschriften/Bestätigungen als **Partei**, (2) eigene **Anerkennungen** als
    Publikum. Jeweils mit Inhalt zum Nachlesen."""
    from ..models import DocumentSignoff, Instance
    from .document import instance_document_embeds, render_meta
    out: list[dict] = []
    # (1) Erledigte Freigaben (als benannte Partei)
    signed = (
        db.query(DocumentSignoff)
        .filter(DocumentSignoff.signer_object_id == user.object_id,
                DocumentSignoff.status == "signed", DocumentSignoff.is_active == True)
        .order_by(DocumentSignoff.id.desc()).all()
    )
    for so in signed:
        doc = db.query(Document).filter(
            Document.id == so.document_id, Document.is_active == True).first()
        if not doc:
            continue
        order = db.query(Order).filter(Order.id == so.order_id).first()
        obj_nr, _ = render_meta(db, order) if order else (None, None)
        out.append({
            "kind": "signoff",
            "title": (doc.content or {}).get("title") or "Dokument",
            "object_number": obj_nr,
            "acted_at": so.acted_at,
            "label": "Unterschrieben" if so.action == "sign" else "Bestätigt",
            "content": doc.content,
        })
    # (2) Erledigte Anerkennungen (als Publikum) – Inhalt aus der Versions-Instanz.
    for r in acknowledgements_for(db, user):
        version = r["version_object_id"]
        content = None
        inst = db.query(Instance).filter(Instance.object_id == version).first()
        if inst is not None:
            embeds = instance_document_embeds(db, inst)
            if embeds and embeds[0].content is not None:
                content = embeds[0].content.model_dump()
        out.append({
            "kind": "ack",
            "title": r["title"],
            "object_number": version,
            "acted_at": r["accepted_at"],
            "label": "Anerkannt",
            "content": content,
        })
    out.sort(key=lambda x: (x["acted_at"] is not None, x["acted_at"]), reverse=True)
    return out


def acknowledgements_for(db: Session, user: UserProfile) -> list[dict]:
    """Alle Bestätigungen eines Nutzers (neueste zuerst) – für den Benutzer-ERP-Datensatz
    («AGB akzeptiert am … · Stand Objektnummer …»)."""
    rows = (
        db.query(DocumentAcknowledgement)
        .filter(DocumentAcknowledgement.user_id == user.id,
                DocumentAcknowledgement.is_active == True)
        .order_by(DocumentAcknowledgement.accepted_at.desc())
        .all()
    )
    return [{
        "kind": r.kind,
        "title": _KIND_LABELS.get(r.kind, r.kind.replace("_", " ").upper()),
        "version_object_id": r.version_object_id,
        "accepted_at": r.accepted_at,
    } for r in rows]
