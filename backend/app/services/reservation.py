"""Mengengenaue Instanz-Reservierung **ohne Teilung** (REA-konform).

Die universelle Objektnummer einer Instanz ist physisch (Etikett/QR an den Teilen) –
sie darf sich **nie** ändern und eine Instanz darf **nie** in eine zweite Instanz mit
eigener Nummer aufgeteilt werden. Eine Charge wird daher nicht mehr „geteilt"; statt-
dessen merkt sich die Instanz **pro Auftrag eine Menge** (``instances.reservations`` =
``{auftrag_db_id: menge}``). Die denormalisierte Summe (``reserved_quantity``) macht die
Verfügbarkeit per SQL-Aggregat zählbar.

Frei verfügbar (für andere Aufträge) = ``quantity − reserved_quantity``. So bleibt eine
Charge von 1000 Schrauben mit 970 frei, auch wenn 30 für einen Auftrag reserviert sind.
"""

from ..models import Instance


def reserved_for(inst: Instance, order_id: int) -> int:
    """Wie viel dieser Instanz für den gegebenen Auftrag reserviert ist."""
    return int((inst.reservations or {}).get(str(order_id), 0))


def free_qty(inst: Instance) -> int:
    """Frei verfügbare Restmenge (gesamt − reserviert)."""
    return (inst.quantity or 0) - (inst.reserved_quantity or 0)


def reserve(inst: Instance, order_id: int, qty: int) -> None:
    """``qty`` der Instanz für ``order_id`` reservieren (additiv). Aktualisiert die Summe
    und den Einzel-Zeiger; die Instanz wird NICHT geteilt (Objektnummer bleibt)."""
    if qty <= 0:
        return
    m = dict(inst.reservations or {})
    m[str(order_id)] = m.get(str(order_id), 0) + qty
    inst.reservations = m
    inst.reserved_quantity = sum(int(v) for v in m.values())
    inst.reserved_for_order_id = order_id if len(m) == 1 else None


def release(inst: Instance, order_id: int) -> int:
    """Die Reservierung eines Auftrags vollständig lösen. Liefert die gelöste Menge."""
    m = dict(inst.reservations or {})
    qty = int(m.pop(str(order_id), 0))
    inst.reservations = m
    inst.reserved_quantity = sum(int(v) for v in m.values())
    inst.reserved_for_order_id = next((int(k) for k in m), None) if len(m) == 1 else None
    return qty


def consume(inst: Instance, order_id: int, qty: int) -> None:
    """``qty`` aus der Instanz **verbrauchen**: Gesamtmenge mindern und die Reservierung
    des Auftrags entsprechend reduzieren (die entnommenen Stück sind über die Fachtabelle
    – Pick/Verkauf – belegt; es entsteht KEINE neue Instanz)."""
    inst.quantity = max(0, (inst.quantity or 0) - qty)
    m = dict(inst.reservations or {})
    left = int(m.get(str(order_id), 0)) - qty
    if left > 0:
        m[str(order_id)] = left
    else:
        m.pop(str(order_id), None)
    inst.reservations = m
    inst.reserved_quantity = sum(int(v) for v in m.values())
    inst.reserved_for_order_id = next((int(k) for k in m), None) if len(m) == 1 else None
