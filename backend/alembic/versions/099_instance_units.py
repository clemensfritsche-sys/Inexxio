"""Jedes Stück bekommt eine eigene Nummer: ``instances.units``.

Eine Charge war bisher eine Menge unter EINER Nummer («100000101 · 4 Stk»). Welches der
vier Stück gerade in einer Abweichung steckt, liess sich nicht sagen – es gab nur Summen.
Ab jetzt trägt jedes Stück ``100000101-1`` … ``-4``.

**Ohne neue Datensätze**: die Stücke wohnen als **Läufe** in der Instanz (Normalfall = EINE
Zeile für 1000 Schrauben), Schreibstelle ist ausschliesslich ``services/units.py``.

**Kein Backfill**: ``NULL`` heisst «noch keine Nummern vergeben»; ``units.ensure`` eröffnet
sie beim ersten Zugriff aus dem heutigen Stand (Eröffnungsbilanz wie im Material-Journal,
ADR 007). Eine nachgerechnete Historie wäre gelogen.

Revision ID: 099
Revises: 098
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "099"
down_revision = "098"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    # Idempotent: das Lifespan-Sicherheitsnetz legt die Spalte notfalls schon an (Lehre aus
    # Migration 090) – dann darf diese Revision nicht an «column already exists» scheitern.
    if not _has_column("instances", "units"):
        op.add_column("instances",
                      sa.Column("units", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    if _has_column("instances", "units"):
        op.drop_column("instances", "units")
