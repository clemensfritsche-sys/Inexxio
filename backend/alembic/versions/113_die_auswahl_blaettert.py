"""Die Stück-Auswahl blättert — ein Index für die Vorauswahl.

**Warum ein Index eine fachliche Änderung begleitet.** Die «Lager»-Zeile schlägt beim
Öffnen die ältesten *im Regal liegenden* Stücke vor (Testnotiz #739/#740). Diese Frage –
«die ältesten Stücke dieser Instanz in diesem Zustand» – ist genau die Form, für die ein
zusammengesetzter Index gebaut ist; ohne ihn sortiert PostgreSQL sie jedes Mal neu.

**Gemessen, nicht behauptet** (50 000 Einzelinstanzen eines Artikels, davon 10 frei):
die Vorauswahl fällt von **15,3 ms auf 1,2 ms**. Die übrigen Abfragen der Seite ändern
sich nicht – sie lesen ohnehin alles (Aggregat, Gesamtzahl) oder nur 60 Zeilen.

Die Spaltenreihenfolge ist die der Frage: erst **wessen** Stücke (``instance_id``), dann
**welche** (``status``), dann **die ältesten zuerst** (``id``). Umgekehrt sortiert wäre er
für genau diese Abfrage nutzlos.

Idempotent (``IF NOT EXISTS``), damit ein Deploy, bei dem das Lifespan-Netz zuerst
gegriffen hat, nicht auf «existiert bereits» aufläuft – die Lehre aus Migration 090.

Revision ID: 113
Revises: 112
"""

from alembic import op

revision = "113"
down_revision = "112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_instance_units_instance_status "
        "ON instance_units (instance_id, status, id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_instance_units_instance_status")
