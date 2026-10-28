"""►►► **Ein Log für alles** (``audit_log``). ◄◄◄

Jede Schreibstelle protokolliert: wer, was, wann, vorher und nachher, und in wessen Namen
(``on_behalf``: leer = der Mensch selbst, ``ai`` = die KI für ihn, ``system`` = eine
Freigabe, die das System übernommen hat). Jede schreibende Anfrage ans ERP hinterlässt
zusätzlich eine Zeile (``main.audit_writes``) – so fehlt keine Stelle, auch wenn sie selbst
nichts Genaueres schreibt. Auch jeder KI-Aufruf ist eine Zeile (``services/ai``).
"""

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
    on_behalf: str | None = None,
) -> AuditLog:
    """Eine Zeile ins Log – in der Transaktion des Aufrufers."""
    entry = AuditLog(
        object_id=object_id,
        table_name=table_name,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        user_id=user_id,
        on_behalf=on_behalf,
    )
    db.add(entry)
    db.flush()
    return entry
