"""079 – Pflicht-Bewegungen auflösen: aus der Sperre ``locked`` wird die Rolle ``companion``.

Die automatisch erzeugten Bewegungen rund um Beschaffung (Wareneingang) und Verkauf
(Versand zum Kunden) waren **gesperrt**: nicht löschbar, nicht verschiebbar, nur das Ziel
editierbar – und sie wurden bei jeder Strukturänderung neu abgeleitet und umpositioniert.
Wer sie nicht brauchte (Abholung durch den Kunden, Streckengeschäft, digitale Lieferung),
konnte sie nicht entfernen: der nächste Sync legte sie wieder an.

Ab jetzt sind es **ganz normale Schritte** – löschbar, verschiebbar, editierbar. Das System
**sät** sie nur noch einmalig beim Anlegen des auslösenden Schritts
(``services/process_steps.seed_companion_movements``); was der Nutzer löscht, bleibt gelöscht.

Was die Spalte weiterhin trägt, ist die **Rolle** – zwei echte Fachwirkungen, die von der
Sperre unabhängig sind:

* ``mode='customer'`` → das Ziel ist der Kunde des Verkaufs (``movement.record_movement``),
* Begleiter sind von der Fehlmengen-Prüfung ausgenommen (``process.step_shortfalls``) – ohne
  diese Ausnahme wäre der Versand blockiert, sobald der Verkauf bezahlt ist (die Ware gilt
  dann als «verkauft», also aus Sicht des freien Bestands weg). Genau das war der Bug, den
  Migration 074 für den Shop-Pfad repariert hat; die Ausnahme muss erhalten bleiben.

Darum **eine eigene Spalte** und nicht einfach ``mode``: dessen Default ist ``'supplier'`` –
jede vom Nutzer angelegte Bewegung würde sonst fälschlich als Wareneingang gelten.

**Additiv, nicht umbenennend.** ``locked`` bleibt vorerst stehen. Während eines Cloud-Run-
Rollouts serviert die alte Revision noch; die liest ``locked`` und würde auf eine
umbenannte/gedroppte Spalte laufen. Die neue Spalte hat einen ``server_default``, sodass
umgekehrt auch INSERTs der alten Revision gültig bleiben. ``locked`` wird in einem
**Folge-Deploy** entfernt (gleiches Muster wie Migration 078).

Idempotent: ein erneuter Lauf ist ein No-op.

Revision ID: 079
Revises: 078
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '079'
down_revision = '078'
branch_labels = None
depends_on = None

TABLE = "article_process_steps"


def _cols(insp) -> set[str]:
    return {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE not in set(insp.get_table_names()):
        return
    cols = _cols(insp)

    if "companion" not in cols:
        op.add_column(TABLE, sa.Column("companion", sa.Boolean(), nullable=False,
                                       server_default=sa.text("false")))

    # Bestand übernehmen: exakt die bisher gesperrten Schritte waren die Begleiter.
    if "locked" in cols:
        op.execute(f"UPDATE {TABLE} SET companion = locked WHERE companion IS DISTINCT FROM locked")

    # Alt-Bestand «Versand zum Lieferanten» (entfiel im Juli 2026, siehe process_steps.py):
    # gesperrte Bewegungen mit einem **Personen-Ziel** – genau so erkannte sie die alte
    # ``sync_locked_movements`` (sie fielen aus dem Wareneingang-Pool und wurden bei jedem
    # Sync deaktiviert). Diesen selbstheilenden Sync gibt es nicht mehr, also hier abschliessen.
    op.execute(f"""
        UPDATE {TABLE}
           SET is_active = false
         WHERE companion = true
           AND step_type = 'movement'
           AND mode <> 'customer'
           AND target_location_type = 'user'
           AND is_active = true
    """)


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE not in set(insp.get_table_names()):
        return
    if "companion" in _cols(insp):
        op.drop_column(TABLE, "companion")
