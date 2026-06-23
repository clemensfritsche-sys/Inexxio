"""Wiederkehrende Vorgänge – ein **Generator** für normale Aufträge.

Deckt Compliance/Termine (ISO 9001 …) und Abos mit DERSELBEN Logik ab:
- **Compliance** (``valid_until`` gesetzt): der Erneuerungs-Auftrag wird
  ``lead_time_days`` **vor** dem Ablauf erzeugt – nie eine Lücke. Bei Abschluss
  rollt ``valid_until`` um ``validity_days`` vor.
- **Abo** (``interval_days`` gesetzt): fester Takt ab ``next_due_at``.

Der erzeugte Auftrag (Entwurf) läuft durch die **gleiche** Prozess-Engine.

Hinweis: Es gibt (noch) keinen eigenen Scheduler – ``spawn_due`` wird beim
App-Start ausgeführt und kann via Endpunkt manuell ausgelöst werden (Phase 2: Cron).
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..models import Order, RecurringOrder
from ..models.base import utcnow
from .admin import log_audit
from .events import emit
from .objects import next_object_id


def due_now(rec: RecurringOrder, today: date) -> bool:
    """Ist (heute) ein neuer Auftrag fällig? (rein, testbar)"""
    if rec.valid_until is not None:                       # Compliance: Vorlaufzeit
        return (rec.valid_until - timedelta(days=rec.lead_time_days or 0)) <= today
    if rec.next_due_at is not None:                       # Abo/Intervall
        return rec.next_due_at <= today
    return False


def _create_order(db: Session, rec: RecurringOrder, today: date) -> Order:
    order = Order(
        object_id=next_object_id(db, "order"),
        status="draft",
        article_id=rec.article_id,
        quantity=rec.quantity,
        process_id=rec.process_id,
        subject_instance_id=rec.subject_instance_id,
        desired_delivery_date=rec.valid_until or rec.next_due_at,
    )
    db.add(order)
    db.flush()
    log_audit(db, "orders", None, f"Auftrag aus wiederkehrendem Vorgang '{rec.name}'",
              None, object_id=order.object_id)
    emit(db, "order.created_recurring", object_type="order", object_id=order.object_id,
         payload={"recurring_id": rec.object_id})
    return order


def spawn_due(db: Session, today: date | None = None) -> list[Order]:
    """Fällige wiederkehrende Vorgänge zu Aufträgen machen (idempotent).

    Solange der zuletzt erzeugte Auftrag offen ist (draft/released), wird KEIN
    weiterer erzeugt. Ist er abgeschlossen, rollt (bei Compliance) ``valid_until``
    vor und der nächste Zyklus kann fällig werden."""
    today = today or date.today()
    created: list[Order] = []
    recs = (
        db.query(RecurringOrder)
        .filter(RecurringOrder.is_active == True, RecurringOrder.status == "released")
        .all()
    )
    for rec in recs:
        if rec.last_order_id:
            last = db.query(Order).filter(Order.object_id == rec.last_order_id).first()
            if last and last.status in ("draft", "released"):
                continue   # läuft noch – nichts Neues erzeugen
            if last and last.status == "completed":
                # Erfolgreich erneuert: Gültigkeit vorrollen, Verknüpfung freigeben.
                if rec.valid_until and rec.validity_days:
                    rec.valid_until = max(rec.valid_until, today) + timedelta(days=rec.validity_days)
            rec.last_order_id = None
        if due_now(rec, today):
            order = _create_order(db, rec, today)
            rec.last_order_id = order.object_id
            rec.last_run_at = utcnow()
            if rec.interval_days:
                base = rec.next_due_at or today
                rec.next_due_at = base + timedelta(days=rec.interval_days)
            created.append(order)
    db.commit()
    return created
