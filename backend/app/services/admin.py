"""Service layer for admin operations."""

from sqlalchemy.orm import Session

from ..models import AuditLog, CompanySettings


def get_or_create_settings(db: Session) -> CompanySettings:
    """«Die Firma» – der **Hauptsitz**, angelegt falls die Datenbank leer ist.

    Seit Migration 090 trägt ``company_settings`` mehrere Zeilen (eine je Standort). Die
    Rechtsidentität und die Systemkonfiguration hängen am Hauptsitz, und genau den meinen
    alle bestehenden Aufrufer dieser Funktion – deshalb bleibt der Name und es ändert sich
    an keiner Aufrufstelle etwas. Die Auflösung selbst steht in ``services/sites.py``,
    damit «welcher Standort ist gemeint» nur EINE Antwort hat.

    Wer die Anschrift eines **bestimmten** Standorts braucht (Bewegungs-Ziel, Halter-
    Label), nimmt ``sites.by_object_id`` – nicht diese Funktion.

    (Import bewusst lazy: ``sites`` holt sich von hier ``log_audit``.)"""
    from .sites import primary
    return primary(db)


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
