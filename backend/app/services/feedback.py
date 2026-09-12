"""Testnotizen – die EINE Stelle für Sichtbarkeit, Anlage und Abschluss.

Fachlich ist das Modul absichtlich klein: eine Notiz ist ein Zettel mit Kontext, kein
Geschäftsvorgang (keine Objektnummer, kein Event-Strom, kein Audit-Log – sonst wanderte
Entwicklungs-Rauschen in die ökonomische Wahrheit des Systems).

Zwei Regeln tragen das Modul:

1. **Nur ausserhalb der Produktion** (``is_enabled``). Die Notizfunktion ist ein
   Werkzeug für die Testumgebung; in der Produktion existiert sie schlicht nicht.
2. **Melden darf jede angemeldete Rolle, sehen nur die eigenen** – Personal sieht
   alles (``visible_query``). So kann auch aus Kunden-/Lieferantensicht gemeldet
   werden, ohne dass ein Kunde die Testnotizen anderer liest.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from ..core.config import get_settings
from ..models import FeedbackNote, UserProfile
from ..schemas.feedback import FeedbackCreate, FeedbackNoteResponse, FeedbackUpdate
from . import people

STAFF_ROLES = ("admin", "employee")


def is_enabled() -> bool:
    """Testumgebung? Die Produktion kennt keine Notizfunktion."""
    return get_settings().app_env != "production"


def _is_staff(user: UserProfile) -> bool:
    return user.role in STAFF_ROLES


def visible_query(db: Session, user: UserProfile) -> Query:
    """Personal sieht alle Notizen, alle anderen ausschliesslich ihre eigenen."""
    q = db.query(FeedbackNote).filter(FeedbackNote.is_active == True)  # noqa: E712
    if not _is_staff(user):
        q = q.filter(FeedbackNote.created_by == user.id)
    return q


def list_notes(
    db: Session, user: UserProfile, route: Optional[str] = None, status: Optional[str] = None
) -> list[FeedbackNote]:
    """Notizen, neueste zuerst. ``route`` filtert auf die aktuelle Seite (Pin-Anzeige);
    der Pfad wird OHNE Query-String verglichen, damit ein Pin auch dann wieder
    erscheint, wenn ein anderer Datensatz offen ist."""
    q = visible_query(db, user)
    if status:
        q = q.filter(FeedbackNote.status == status)
    if route:
        path = route.split("?")[0]
        q = q.filter(or_(FeedbackNote.route == path, FeedbackNote.route.like(f"{path}?%")))
    return q.order_by(FeedbackNote.id.desc()).limit(200).all()


def create_note(db: Session, user: UserProfile, data: FeedbackCreate) -> FeedbackNote:
    note = FeedbackNote(
        body=data.body.strip(),
        route=(data.route or "")[:500],
        target_object_id=data.target_object_id,
        anchor=data.anchor.model_dump() if data.anchor else None,
        context=data.context.model_dump() if data.context else None,
        created_by=user.id,
    )
    db.add(note)
    db.flush()
    return note


def apply_update(
    db: Session, note: FeedbackNote, user: UserProfile, data: FeedbackUpdate
) -> FeedbackNote:
    """Status/Begründung setzen. ``resolved_*`` wird nur beim Abschluss gestempelt –
    ein Wiederöffnen räumt den Stempel weg, damit er nie etwas Falsches behauptet."""
    if data.resolution is not None:
        note.resolution = data.resolution.strip() or None
    if data.status is not None and data.status != note.status:
        note.status = data.status
        if data.status == "open":
            note.resolved_at, note.resolved_by = None, None
        else:
            note.resolved_at = datetime.now(timezone.utc)
            note.resolved_by = user.id
    db.flush()
    return note


def delete_note(db: Session, note: FeedbackNote) -> None:
    """Soft-Delete (Hausregel: nie hart löschen). Für den Melder ist die Notiz weg."""
    note.is_active = False
    db.flush()


def delete_many(db: Session, user: UserProfile, scope: str) -> int:
    """Aufräumen: ``done`` entfernt nur Abgehaktes/Verworfenes, ``all`` setzt zurück.
    Beides läuft über ``visible_query`` – wer nur seine eigenen Notizen sieht, kann
    auch nur seine eigenen löschen."""
    if scope not in ("done", "all"):
        raise ValueError("scope must be 'done' or 'all'")
    q = visible_query(db, user)
    if scope == "done":
        q = q.filter(FeedbackNote.status != "open")
    return q.update({FeedbackNote.is_active: False}, synchronize_session=False)


def to_response(db: Session, note: FeedbackNote, user: UserProfile) -> FeedbackNoteResponse:
    """Antwort inkl. der zwei abgeleiteten Felder: Melder-Name und «darf ich ran?»."""
    return FeedbackNoteResponse(
        **{c: getattr(note, c) for c in (
            "id", "status", "body", "route", "target_object_id", "anchor", "context",
            "resolution", "resolved_at", "created_at", "created_by",
        )},
        author_name=people.name_by_id(db, note.created_by) or "",
        mine=_is_staff(user) or note.created_by == user.id,
    )
