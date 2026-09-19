"""Wann wurde storniert — `deals.cancelled_on`

Der Beleg kennt seit jeher das **Zusagedatum** (`agreed_on`) und weiss, dass er storniert
ist (`stage`) – aber nicht **wann**. Solange unten im Abschnitt die ganzen Angebotszeilen
standen, fiel es nicht auf; seit er eine **Chronik** ist (Testnotiz #918: «wann wurde
offeriert, wann wurde die Offerte angenommen»), ist es die eine fehlende Zeile.

`updated_at` ist die Antwort **nicht**: sie wandert bei jeder späteren Änderung mit, und
ein Storno, dessen Datum sich bewegt, ist kein Datum.

`NULL` heisst «nicht storniert» – der Normalfall, und keine fehlende Angabe.

Revision ID: 133
Revises: 132
"""

from alembic import op
import sqlalchemy as sa

revision = "133"
down_revision = "132"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    # **Idempotent je Spalte** – die dev-Datenbank kennt kein `alembic upgrade`, dort legt
    # das Spalten-Netz in `main.py` nach (die Lehre aus Migration 129).
    if not _has_column("deals", "cancelled_on"):
        op.add_column("deals", sa.Column("cancelled_on", sa.Date(), nullable=True))


def downgrade() -> None:
    if _has_column("deals", "cancelled_on"):
        op.drop_column("deals", "cancelled_on")
