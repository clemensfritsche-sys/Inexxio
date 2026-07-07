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

from ..models import DocumentAcknowledgement, UserProfile
from . import legal
from .admin import get_or_create_settings, log_audit
from .events import emit

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


def pending_documents(db: Session, user: UserProfile) -> list[dict]:
    """Alle für diesen Nutzer noch offenen Pflicht-Bestätigungen (aktuelle Version, ungeprüft)."""
    settings = get_or_create_settings(db)
    out: list[dict] = []
    for kind in required_kinds(settings, user.role):
        resolved = legal.resolve(db, kind)
        if not resolved or not resolved.get("object_number"):
            continue   # kein gültiges Dokument hinterlegt → nichts zu bestätigen
        if _has_ack(db, user.id, kind, resolved["object_number"]):
            continue
        out.append({
            "kind": kind,
            "title": _label(kind, resolved.get("content")),
            "object_number": resolved["object_number"],
            "document_date": resolved.get("document_date"),
            "content": resolved.get("content"),
        })
    return out


def acknowledge(db: Session, user: UserProfile, kind: str) -> None:
    """Die **aktuelle** Version von ``kind`` für den Nutzer als bestätigt festhalten
    (idempotent). Committet."""
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
