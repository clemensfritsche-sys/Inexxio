"""objekttypen table + referenz columns on prozess_schritte

Revision ID: 013
Revises: 012
Create Date: 2026-06-09
"""
from alembic import op

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS objekttypen (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            farbe VARCHAR(20) NOT NULL DEFAULT 'blue',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        ALTER TABLE prozess_schritte
            ADD COLUMN IF NOT EXISTS referenz_objekt_id BIGINT
                REFERENCES objects(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS referenz_menge INTEGER NOT NULL DEFAULT 1
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE prozess_schritte DROP COLUMN IF EXISTS referenz_menge")
    op.execute("ALTER TABLE prozess_schritte DROP COLUMN IF EXISTS referenz_objekt_id")
    op.execute("DROP TABLE IF EXISTS objekttypen")
