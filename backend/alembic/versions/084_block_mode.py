"""084 – «Sperren» als reversibles Gegenstück zum Verschrotten.

Nicht immer soll ein Teil endgültig weg: eine defekte Maschine wartet auf ihre Wartung
und muss so lange **gesperrt** sein – vorhanden, aber nicht verwendbar.

Modelliert auf der **Qualitäts-Achse** (``instances.quality = 'blocked'``), nicht auf der
Verbleibs-Achse: «wo ist es» ändert sich durch eine Sperre nicht, «darf man es verwenden»
schon. Weil ``inventory.in_stock_clauses()`` beides verlangt (passed UND in_stock), fällt
eine gesperrte Instanz automatisch aus FIFO, Verfügbarkeit und Bestandszählung – ohne eine
einzige zusätzliche Abfrage. Und weil ``quality`` ohnehin veränderlich ist, ist die Sperre
von Natur aus rücknehmbar (``services/scrap.unblock``).

Schema-seitig braucht es dafür nur **eine** Spalte: ``disposals.mode`` unterscheidet, ob
die Marker-Zeile ein Verschrotten oder ein Sperren war. ``quality`` ist bereits ein freies
VARCHAR ohne CHECK – der neue Wert passt ohne Typänderung hinein.

Revision ID: 084
Revises: 083
Create Date: 2026-07-27
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '084'
down_revision = '083'
branch_labels = None
depends_on = None

TABLE = "disposals"
COLUMN = "mode"


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE not in set(insp.get_table_names()):
        return
    if COLUMN not in {c["name"] for c in insp.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(
            COLUMN, sa.String(length=10), server_default="scrap", nullable=False))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if TABLE in set(insp.get_table_names()):
        if COLUMN in {c["name"] for c in insp.get_columns(TABLE)}:
            op.drop_column(TABLE, COLUMN)
