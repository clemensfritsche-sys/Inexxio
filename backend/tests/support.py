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
