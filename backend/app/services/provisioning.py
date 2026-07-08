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
(``services/resource.py`` – Komponente → Produkt-Instanz, Werkzeug → Arbeitsplatz). NEU
über diesen Reconciler verdrahtet ist der **Schrottplatz**: verschrottete (ganze)
Instanzen wandern automatisch an den Ausschuss-Lagerort (no-op, wenn schon dort).
"""

from sqlalchemy.orm import Session

from ..models import CompanySettings, Instance, StorageLocation
from . import location_split
from .objects import next_object_id


def reconcile_to(inst: Instance, to_type: str, to_id: int) -> bool:
    """Die GANZE Instanz an (``to_type``, ``to_id``) bringen. **No-op**, wenn sie
    (ausschliesslich) schon dort liegt. Gibt zurück, ob tatsächlich bewegt wurde.

    Das ist der eine «Ist ↔ Soll»-Abgleich: eine verteilte Charge wird dabei am Ziel
    wieder zusammengeführt (``location_split.set_single``). Teilmengen-Bewegungen laufen
    bewusst NICHT hierüber, sondern auftragsgetrieben über den Bewegungs-Schritt."""
    to_id = int(to_id)
    if (inst.location_type, inst.location_id) == (to_type, to_id) and not inst.locations:
        return False   # schon am Ziel → no-op
    location_split.set_single(inst, to_type, to_id)
    return True


def resolve_scrap_location(db: Session) -> int:
    """Objektnummer des Ausschuss-/Schrott-Lagerplatzes.

    Konfigurierbar über ``company_settings.default_scrap_location_id``; fehlt der Eintrag
    (oder zeigt er ins Leere), wird EINMALIG ein Lagerplatz «Schrottplatz» angelegt und die
    Nummer am Unternehmen hinterlegt (idempotent – «keine herrenlosen Teile»). Committet NICHT."""
    settings = db.query(CompanySettings).first()
    configured = getattr(settings, "default_scrap_location_id", None) if settings else None
    if configured:
        exists = (
            db.query(StorageLocation.id)
            .filter(StorageLocation.object_id == configured, StorageLocation.is_active == True)
            .first()
        )
        if exists:
            return int(configured)
    loc = StorageLocation(
        object_id=next_object_id(db, "storage_location"), status="released",
        name="Schrottplatz", code="SCHROTT",
        note="Automatisch angelegt für Ausschuss/Verschrottung.",
    )
    db.add(loc)
    db.flush()
    if settings:
        settings.default_scrap_location_id = loc.object_id
    return int(loc.object_id)


def send_to_scrapyard(db: Session, instances: list[Instance], actor_id: int) -> int:
    """Verschrottete (ganze) Instanzen an den Schrottplatz bringen – no-op, wenn schon dort.

    Der Aufrufer übergibt nur die im aktuellen Vorgang GANZ verschrotteten Instanzen: eine
    **Teil-Verschrottung** lässt die gute Restmenge am Lager, wird also NICHT verlagert.
    Gibt die Zahl tatsächlich bewegter Instanzen zurück. Committet NICHT."""
    if not instances:
        return 0
    from .admin import log_audit
    scrap_id = resolve_scrap_location(db)
    moved = 0
    for inst in instances:
        old = f"{inst.location_type}:{inst.location_id}"
        if reconcile_to(inst, "lagerplatz", scrap_id):
            log_audit(db, "instances", "location", f"lagerplatz:{scrap_id}", actor_id,
                      object_id=inst.object_id, old_value=old)
            moved += 1
    return moved
