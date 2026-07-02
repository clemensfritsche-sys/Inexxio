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


def _write(inst: Instance, m: dict) -> None:
    """Reservierungs-Map zurückschreiben + Denormalisierungen (Summe, Einzel-Zeiger)
    konsistent nachziehen – die EINE Stelle, an der die drei Felder gesetzt werden."""
    inst.reservations = m
    inst.reserved_quantity = sum(int(v) for v in m.values())
    inst.reserved_for_order_id = next((int(k) for k in m), None) if len(m) == 1 else None


def reserve(inst: Instance, order_id: int, qty: int) -> None:
    """``qty`` der Instanz für ``order_id`` reservieren (additiv). Aktualisiert die Summe
    und den Einzel-Zeiger; die Instanz wird NICHT geteilt (Objektnummer bleibt)."""
    if qty <= 0:
        return
    m = dict(inst.reservations or {})
    m[str(order_id)] = m.get(str(order_id), 0) + qty
    _write(inst, m)


def release(inst: Instance, order_id: int) -> int:
    """Die Reservierung eines Auftrags vollständig lösen. Liefert die gelöste Menge."""
    m = dict(inst.reservations or {})
    qty = int(m.pop(str(order_id), 0))
    _write(inst, m)
    return qty


def release_all(inst: Instance) -> None:
    """**Alle** Reservierungen einer Instanz lösen. Für terminale Verbleibe (verschrottet):
    ein Teil, das den Bestand verlässt, kann keinen Auftrag mehr beliefern – auch nicht einen
    Eltern-/Fremd-Auftrag, der es reserviert hatte. So wird dessen Fehlmenge **ehrlich** wieder
    sichtbar (statt still von einer toten Reservierung „gedeckt" zu bleiben)."""
    _write(inst, {})


def reduce_quantity(inst: Instance, cut: int) -> int:
    """Die Gesamtmenge einer (Chargen-)Instanz um ``cut`` senken (Teil-Verschrottung) – die
    Objektnummer bleibt, es entsteht KEINE neue Instanz. Übersteigen die Reservierungen danach
    die Restmenge, werden sie (grösste zuerst) heruntergetrimmt – die betroffenen Aufträge
    sehen dadurch **ehrlich** eine Fehlmenge (Recovery). Liefert die tatsächlich entfernte Menge."""
    cut = max(0, min(cut, inst.quantity or 0))
    if cut <= 0:
        return 0
    inst.quantity = (inst.quantity or 0) - cut
    m = dict(inst.reservations or {})
    while m and sum(int(v) for v in m.values()) > inst.quantity:
        k = max(m, key=lambda x: int(m[x]))
        over = sum(int(v) for v in m.values()) - inst.quantity
        m[k] = int(m[k]) - over
        if m[k] <= 0:
            del m[k]
    _write(inst, m)
    return cut


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
    _write(inst, m)
