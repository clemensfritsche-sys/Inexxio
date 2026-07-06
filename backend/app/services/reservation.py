"""Mengengenaue Instanz-Reservierung **ohne Teilung** (REA-konform).

Die universelle Objektnummer einer Instanz ist physisch (Etikett/QR an den Teilen) –
sie darf sich **nie** ändern und eine Instanz darf **nie** in eine zweite Instanz mit
eigener Nummer aufgeteilt werden. Eine Charge wird daher nicht mehr „geteilt"; statt-
dessen merkt sich die Instanz **pro Auftrag eine Menge** (``instances.reservations`` =
``{auftrag_db_id: menge}``). Die denormalisierte Summe (``reserved_quantity``) macht die
Verfügbarkeit per SQL-Aggregat zählbar.

Frei verfügbar (für andere Aufträge) = ``quantity − reserved_quantity``. So bleibt eine
Charge von 1000 Schrauben mit 970 frei, auch wenn 30 für einen Auftrag reserviert sind.

**Bruchmengen:** alle Mengen sind ``Decimal`` (kg/m²/m³/l, nicht nur ganze Stück). Die
Reservierungs-Map speichert die Mengen als **String** (JSON-sicher, exakt), gelesen/
geschrieben ausschliesslich über ``services/quantity.py``.
"""

from decimal import Decimal

from ..models import Instance
from .quantity import ZERO, qty_key, qty_sum, to_qty


def _load(inst: Instance) -> dict[str, Decimal]:
    """Reservierungs-Map als ``{auftrag: Decimal}`` einlesen (Werte sind Strings in JSONB)."""
    return {k: to_qty(v) for k, v in (inst.reservations or {}).items()}


def reserved_for(inst: Instance, order_id: int) -> Decimal:
    """Wie viel dieser Instanz für den gegebenen Auftrag reserviert ist."""
    return to_qty((inst.reservations or {}).get(str(order_id), 0))


def free_qty(inst: Instance) -> Decimal:
    """Frei verfügbare Restmenge (gesamt − reserviert)."""
    return to_qty(inst.quantity) - to_qty(inst.reserved_quantity)


def _write(inst: Instance, m: dict) -> None:
    """Reservierungs-Map zurückschreiben + Denormalisierungen (Summe, Einzel-Zeiger)
    konsistent nachziehen – die EINE Stelle, an der die drei Felder gesetzt werden.
    Nicht-positive Einträge werden verworfen; Mengen JSON-sicher als String abgelegt."""
    clean = {k: qty_key(v) for k, v in m.items() if to_qty(v) > 0}
    inst.reservations = clean or None
    inst.reserved_quantity = qty_sum(clean.values())
    inst.reserved_for_order_id = int(next(iter(clean))) if len(clean) == 1 else None


def reserve(inst: Instance, order_id: int, qty) -> None:
    """``qty`` der Instanz für ``order_id`` reservieren (additiv). Aktualisiert die Summe
    und den Einzel-Zeiger; die Instanz wird NICHT geteilt (Objektnummer bleibt)."""
    q = to_qty(qty)
    if q <= 0:
        return
    m = _load(inst)
    m[str(order_id)] = m.get(str(order_id), ZERO) + q
    _write(inst, m)


def release(inst: Instance, order_id: int) -> Decimal:
    """Die Reservierung eines Auftrags vollständig lösen. Liefert die gelöste Menge."""
    m = _load(inst)
    qty = m.pop(str(order_id), ZERO)
    _write(inst, m)
    return qty


def release_all(inst: Instance) -> None:
    """**Alle** Reservierungen einer Instanz lösen. Für terminale Verbleibe (verschrottet):
    ein Teil, das den Bestand verlässt, kann keinen Auftrag mehr beliefern – auch nicht einen
    Eltern-/Fremd-Auftrag, der es reserviert hatte. So wird dessen Fehlmenge **ehrlich** wieder
    sichtbar (statt still von einer toten Reservierung „gedeckt" zu bleiben)."""
    _write(inst, {})


def reduce_quantity(inst: Instance, cut) -> Decimal:
    """Die Gesamtmenge einer (Chargen-)Instanz um ``cut`` senken (Teil-Verschrottung) – die
    Objektnummer bleibt, es entsteht KEINE neue Instanz. Übersteigen die Reservierungen danach
    die Restmenge, werden sie (grösste zuerst) heruntergetrimmt – die betroffenen Aufträge
    sehen dadurch **ehrlich** eine Fehlmenge (Recovery). Liefert die tatsächlich entfernte Menge."""
    cut = min(to_qty(cut), to_qty(inst.quantity))
    if cut <= 0:
        return ZERO
    inst.quantity = to_qty(inst.quantity) - cut
    m = _load(inst)
    while m and qty_sum(m.values()) > to_qty(inst.quantity):
        k = max(m, key=lambda x: m[x])
        over = qty_sum(m.values()) - to_qty(inst.quantity)
        m[k] = m[k] - over
        if m[k] <= 0:
            del m[k]
    _write(inst, m)
    return cut


def consume(inst: Instance, order_id: int, qty) -> None:
    """``qty`` aus der Instanz **verbrauchen**: Gesamtmenge mindern und die Reservierung
    des Auftrags entsprechend reduzieren (die entnommenen Stück sind über die Fachtabelle
    – Pick/Verkauf – belegt; es entsteht KEINE neue Instanz)."""
    q = to_qty(qty)
    inst.quantity = max(ZERO, to_qty(inst.quantity) - q)
    m = _load(inst)
    left = m.get(str(order_id), ZERO) - q
    if left > 0:
        m[str(order_id)] = left
    else:
        m.pop(str(order_id), None)
    _write(inst, m)
