"""Domain-Event-Strom (transaktionaler Outbox).

``emit`` schreibt ein fachliches Ereignis in dieselbe Transaktion wie die
auslösende Zustandsänderung (nur ``flush`` – der Aufrufer committet). So bleibt
der Event-Strom konsistent mit dem Datenbestand. Der Strom ist die Grundlage für
KI-/Automatisierungs-Anbindung und Analytik; Konsumenten lesen ihn vorwärts über
``GET /api/v1/events?after_id=…``.

Konvention für ``event_type``: ``<objekt>.<vorgang>`` in Kleinbuchstaben, z. B.
``order.released``, ``order.completed``, ``inspection.failed``, ``purchase.received``.
"""

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Event


def _json_safe(value):
    """Payload JSONB-tauglich machen: ``Decimal`` (Bruchmengen) → ``float`` (JSON-nativ).

    Der Event-Strom ist für Beobachtbarkeit/Automatisierung – ``float`` genügt hier
    (die verbindliche Menge steht exakt als ``Decimal`` auf den Instanzen). Ohne diese
    Normalisierung bräche ``json.dumps`` beim Schreiben in die JSONB-Spalte an einer Menge."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


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
