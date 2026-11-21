"""Das eine Datum am Auftrag (Projektakte «Aufgaben», Runde 2): «bis» oder «ab», nie beide.

Revision ID: 189
Revises: 188
"""

from alembic import op

revision = "189"
down_revision = "188"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE orders ADD COLUMN date_kind VARCHAR(8)")
    op.execute("ALTER TABLE orders ADD COLUMN date_on DATE")
    op.execute("ALTER TABLE orders ADD CONSTRAINT ck_orders_date CHECK ("
               "(date_kind IS NULL AND date_on IS NULL) OR "
               "(date_kind IN ('until', 'from') AND date_on IS NOT NULL))")


def downgrade() -> None:
    op.execute("ALTER TABLE orders DROP CONSTRAINT IF EXISTS ck_orders_date")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS date_on")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS date_kind")
