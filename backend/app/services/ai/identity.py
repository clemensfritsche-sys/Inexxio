"""Die KI als echter Principal im System (ADR 004, Frage 3).

Ein System-``UserProfile`` mit ``role='ai'`` und eigener Objektnummer. Aktionen der KI
werden IHR zugeschrieben (Audit ``user_id`` / Event ``actor_id`` / ``created_by`` =
KI-User) – «angelegt von User KI», vollständig nachvollziehbar. Die *Rechte* kommen
dagegen per Delegation vom Menschen (siehe ``principal.py``); die eigene Rolle ``'ai'``
ist bewusst in KEINEM ``require_role``-Gate enthalten – autonom kann die KI nur das,
was ihre Tool-Whitelist erlaubt.

Der Firebase-UID-Slot trägt einen Sentinel (kein echtes Login möglich)."""

from sqlalchemy.orm import Session

from ...models import UserProfile
from ..objects import next_object_id

AI_FIREBASE_UID = "system:inexxio-ai"
AI_EMAIL = "ki@system.inexxio.internal"
AI_ROLE = "ai"


def get_ai_user(db: Session) -> UserProfile | None:
    return (
        db.query(UserProfile)
        .filter(UserProfile.firebase_uid == AI_FIREBASE_UID, UserProfile.is_active == True)
        .first()
    )


def ensure_ai_user(db: Session) -> UserProfile:
    """System-KI-User idempotent anlegen (Seeding beim Start, analog Admin-Bootstrap)."""
    user = get_ai_user(db)
    if user:
        # Selbstheilung: Rolle/Objektnummer konsistent halten (z. B. nach Altdaten-Import).
        changed = False
        if user.role != AI_ROLE:
            user.role = AI_ROLE
            changed = True
        if user.object_id is None:
            user.object_id = next_object_id(db, "user")
            changed = True
        if changed:
            db.commit()
        return user
    user = UserProfile(
        firebase_uid=AI_FIREBASE_UID,
        email=AI_EMAIL,
        first_name="Inexxio",
        last_name="KI",
        role=AI_ROLE,
        language="de",
        object_id=next_object_id(db, "user"),
        notification_email=False,
        notification_inapp=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def is_ai_user(user: UserProfile) -> bool:
    return user.firebase_uid == AI_FIREBASE_UID or user.role == AI_ROLE
