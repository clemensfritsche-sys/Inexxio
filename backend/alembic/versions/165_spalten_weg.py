"""Drei Spalten, die kein Modell mehr kennt, gehen weg (Zwei-Deploy-Regel).

``orders.end_status`` (der Endzustand folgt aus ``statuses.DEFAULT_END_STATUS`` und dem
Eigentum), ``user_profiles.department`` und ``job_title`` – entmappt am 28.10.2026, seither
mehrfach ausgerollt.

Revision ID: 165
Revises: 164
"""

from alembic import op

revision = "165"
down_revision = "164"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS end_status")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS department")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS job_title")


def downgrade() -> None:
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS end_status "
               "varchar(30) NOT NULL DEFAULT 'freigegeben'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS department varchar(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS job_title varchar(100)")
