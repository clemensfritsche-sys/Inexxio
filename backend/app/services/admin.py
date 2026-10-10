"""Service layer for admin operations."""

from sqlalchemy.orm import Session

from ..models import AuditLog


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
