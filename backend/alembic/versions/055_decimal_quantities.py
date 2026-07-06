"""Bruchmengen: alle Mengen-Spalten von INTEGER → NUMERIC(14,3).

Bislang waren sämtliche Mengen ganzzahlig – damit liessen sich nur ganze Stück
abrechnen/reservieren. Für kg · m² · m³ · l braucht es **Bruchmengen** (2.5 kg,
0.75 m²). Die Bestands-/FIFO-/Reservierungs-Engine rechnet ab jetzt mit ``Decimal``
(``NUMERIC(14,3)``, drei Nachkommastellen). Einzelteil-Artikel (``unit``) bleiben
fachlich ganzzahlig (das erzwingt die Anwendung), Chargen dürfen Bruchmengen tragen.

Betroffen: instances.quantity/reserved_quantity, orders.quantity, order_lines.quantity,
purchase_orders.quantity, sales.quantity.

Revision ID: 055
Revises: 054
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '055'
down_revision = '054'
branch_labels = None
depends_on = None

# (Tabelle, Spalte) → auf NUMERIC(14,3) heben. USING castet die vorhandenen Integer-Werte.
_TARGETS = (
    ("instances", "quantity"),
    ("instances", "reserved_quantity"),
    ("orders", "quantity"),
    ("order_lines", "quantity"),
    ("purchase_orders", "quantity"),
    ("sales", "quantity"),
)


def _is_numeric(insp, table: str, column: str) -> bool | None:
    if table not in insp.get_table_names():
        return None
    for c in insp.get_columns(table):
        if c["name"] == column:
            return isinstance(c["type"], sa.Numeric) and not isinstance(c["type"], sa.Integer)
    return None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table, column in _TARGETS:
        present = _is_numeric(insp, table, column)
        if present is None or present:
            continue   # Tabelle/Spalte fehlt oder ist bereits numeric – idempotent
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} '
            f'TYPE NUMERIC(14,3) USING {column}::numeric(14,3)'
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table, column in _TARGETS:
        if table not in insp.get_table_names():
            continue
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} '
            f'TYPE INTEGER USING round({column})::integer'
        )
