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

from ..core.database import json_safe as _json_safe
from ..models import Event

# Der Event-Strom ist für Beobachtbarkeit/Automatisierung – ``float`` genügt hier (die
# verbindliche Menge steht exakt als ``Decimal`` auf den Instanzen). Die Normalisierung
# selbst steht bewusst NICHT hier, sondern an der Grenze zur Datenbank
# (``core.database.json_safe``): sie gilt für ALLE JSONB-Spalten, nicht nur für Events.
# Der Aufruf unten bleibt trotzdem stehen – so ist die Payload schon im Objekt normalisiert
# und ein Leser sieht dieselbe Form wie die Datenbank.


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
        payload=_json_safe(payload) if payload is not None else None,
        actor_id=actor_id,
    )
    db.add(ev)
    db.flush()
    return ev
