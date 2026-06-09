"""add schritt_typ to prozess_schritte

Revision ID: 014
Revises: 013
Create Date: 2026-06-09
"""
from alembic import op

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE prozess_schritte
            ADD COLUMN IF NOT EXISTS schritt_typ VARCHAR(20) NOT NULL DEFAULT 'ressource'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE prozess_schritte DROP COLUMN IF EXISTS schritt_typ")
