"""Gemeinsame Hilfen der Wächter — bewusst winzig, bewusst ohne eigene Regel.

Was hier steht, ist **Bedienung**, keine Fachaussage: die Tests sollen die echten
Dienstpfade rufen, nicht deren Regeln nachbauen.
"""

from typing import Any, Optional
from app.services import order_state


def per_unit(
    db, *, order, step, instance_object_id: int,
    values: Optional[dict[str, Any]] = None,
) -> dict[str, dict[str, Any]]:
    """Ein Wertesatz → **je gezogener Einzelinstanz einer**.

    Genau das tut auch die Oberfläche, nur mit verschiedenen Werten je Stück: sie fragt,
    **welche** Stücke gezogen sind (``group='sample'``), und füllt für jedes ein
    Formular. Hier wird derselbe Satz eingetragen, weil die Tests am Ablauf interessiert
    sind und nicht an den Zahlen darin.

    Die Nummern kommen aus derselben Quelle wie die Erwartung des Servers – ein zweiter
    Weg, sie zu bestimmen, wäre ein zweiter Massstab.
    """

    numbers = order_state.held_numbers(
        db, order, step, instance_object_id=instance_object_id, group="sample",
    )
    return {n: dict(values or {"ok": True}) for n in numbers}


def after_save(db) -> None:
    """**Die Handlung ist gespeichert** – was danach hinausgeht (``core/outside.after``), geht
    jetzt, in dieser zurückrollbaren Sitzung. Der Versand läuft im Betrieb in eigener Sitzung
    über ``send_due`` (``mailbox.send_after``); hier geht jede wartende Mail über dieselbe
    Stelle ``mailbox.send`` – auch mit einem nachgebildeten Postfach."""
    from app.models import Message
    from app.services import mailbox
    db.flush()
    for _, fn in db.info.pop("outside_after", []):
        if fn is not mailbox._send_due_alone:
            fn()
            continue
        for msg in db.query(Message).filter(Message.outgoing.is_(True),
                                            Message.is_active.is_(True)).order_by(Message.id):
            mailbox.send(db, msg)
