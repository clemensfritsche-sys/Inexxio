"""Reconciler «Bereitstellungsort» – Bewegung wird ABGELEITET, nicht orchestriert.

Jeder Schritttyp deklariert in ``domain/event_types.py`` seinen **Bereitstellungsort**
(wohin sein Subjekt/seine Inputs physisch müssen). Dieses Modul ist die EINE Stelle, die
Ist-Standort ↔ Soll vergleicht und die minimal nötige Bewegung erzeugt:

  • schon am Ziel        → gar nichts (**no-op**),
  • woanders             → ganze Instanz ans Ziel verlagern,
  • Charge/Teilmengen    → auftragsgetrieben über den Bewegungs-Schritt
                           (``location_split.move``) – NICHT hier.

Heute laufen Wareneingang/Versand/Kunde über die gesperrten Pflicht-Bewegungen
(``services/process_steps.py``) und Verbrauch/Betriebsmittel über den Ressourcen-Schritt
(``services/resource.py`` – Komponente → Produkt-Instanz, Werkzeug → Arbeitsplatz).

**Verschrotten** hat KEINEN Bereitstellungsort (``PROV_NOWHERE``): ein verschrottetes Teil
verlässt den Bestand endgültig und wird **standortlos** – das erledigt ``services/scrap.py``
über ``location_split.clear`` (kein eigener Schrottplatz-Lagerort mehr).
"""

from ..models import Instance
from . import location_split


def reconcile_to(inst: Instance, to_type: str, to_id: int | None,
                 to_place: dict | None = None) -> bool:
    """Die GANZE Instanz an das Ziel bringen. **No-op**, wenn sie (ausschliesslich) schon
    dort liegt. Gibt zurück, ob tatsächlich bewegt wurde.

    Das ist der eine «Ist ↔ Soll»-Abgleich: eine verteilte Charge wird dabei am Ziel
    wieder zusammengeführt. Teilmengen-Bewegungen laufen bewusst NICHT hierüber, sondern
    auftragsgetrieben über den Bewegungs-Schritt. Ein **Ort** (``to_type='place'``) wird
    über seine Adresse identifiziert, nicht über eine Objektnummer."""
    if location_split.is_at(inst, to_type, to_id, to_place):
        return False   # schon am Ziel → no-op
    location_split.set_target(inst, to_type, to_id, to_place)
    return True
