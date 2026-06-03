"""Service layer for admin operations."""

from sqlalchemy.orm import Session

from ..models.admin import CompanySettings
from ..models.audit import AuditLog, Notification, UserProfile


def get_or_create_settings(db: Session) -> CompanySettings:
    """Return the singleton company settings row, creating it if absent."""
    settings_obj = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    if not settings_obj:
        settings_obj = CompanySettings(id=1)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return settings_obj


def create_notification(
    db: Session,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    link: str | None = None,
) -> Notification:
    """Create an in-app notification for a user."""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        link=link,
    )
    db.add(notification)
    db.flush()
    return notification


def log_audit(
    db: Session,
    table_name: str,
    field_name: str | None,
    new_value: str | None,
    user_id: int | None,
    object_id: int | None = None,
    old_value: str | None = None,
) -> AuditLog:
    """Record an audit log entry."""
    entry = AuditLog(
        object_id=object_id,
        table_name=table_name,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id,
    )
    db.add(entry)
    db.flush()
    return entry


def get_user_by_firebase_uid(db: Session, uid: str) -> UserProfile | None:
    """Fetch a user profile by Firebase UID."""
    return (
        db.query(UserProfile)
        .filter(UserProfile.firebase_uid == uid, UserProfile.is_active == True)
        .first()
    )
