"""Domain-Event-Strom (transaktionaler Outbox).

``emit`` schreibt ein fachliches Ereignis in dieselbe Transaktion wie die
auslösende Zustandsänderung (nur ``flush`` – der Aufrufer committet). So bleibt
der Event-Strom konsistent mit dem Datenbestand. Der Strom ist die Grundlage für
KI-/Automatisierungs-Anbindung und Analytik; Konsumenten lesen ihn vorwärts über
``GET /api/v1/events?after_id=…``.

Konvention für ``event_type``: ``<objekt>.<vorgang>`` in Kleinbuchstaben, z. B.
``order.released``, ``order.completed``, ``inspection.failed``, ``purchase.received``.
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Event


def emit(
    db: Session,
    event_type: str,
    *,
    object_type: str,
    object_id: Optional[int] = None,
    payload: Optional[dict] = None,
    actor_id: Optional[int] = None,
) -> Event:
    """Ein Domain-Event anhängen (append-only). Committet NICHT."""
    ev = Event(
        event_type=event_type,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        actor_id=actor_id,
    )
    db.add(ev)
    db.flush()
    return ev
