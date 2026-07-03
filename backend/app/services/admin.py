"""Service layer for admin operations."""

from sqlalchemy.orm import Session

from ..models import AuditLog, CompanySettings


def get_or_create_settings(db: Session) -> CompanySettings:
    """Return the singleton company settings row, creating it if absent.

    Das Unternehmen ist ein vollwertiger ERP-Datensatz: fehlt die universelle
    Objektnummer noch, wird sie hier **lazy** vergeben (einmalig, race-arm dank
    Sequence) und committet – so erscheint die Firma im ERP-Feed als «Unternehmen»."""
    settings_obj = db.query(CompanySettings).filter(CompanySettings.id == 1).first()
    if not settings_obj:
        settings_obj = CompanySettings(id=1)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    if settings_obj.object_id is None:
        from .objects import next_object_id
        settings_obj.object_id = next_object_id(db, "organization")
        db.commit()
        db.refresh(settings_obj)
    return settings_obj


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
