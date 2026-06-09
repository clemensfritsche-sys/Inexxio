"""add parent_instanz_id and parent_schritt_position to objects

Revision ID: 015
Revises: 014
Create Date: 2026-06-09
"""
from alembic import op

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE objects
            ADD COLUMN IF NOT EXISTS parent_instanz_id BIGINT REFERENCES objects(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS parent_schritt_position INTEGER
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE objects
            DROP COLUMN IF EXISTS parent_schritt_position,
            DROP COLUMN IF EXISTS parent_instanz_id
    """)
