"""Add unified Objekt+Prozess columns to objects and prozess_schritte

Revision ID: 012
Revises: 011
"""
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.execute("""
        ALTER TABLE objects
            ADD COLUMN IF NOT EXISTS stamm_id    BIGINT REFERENCES objects(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS name        VARCHAR(255),
            ADD COLUMN IF NOT EXISTS obj_status  VARCHAR(30) DEFAULT 'ENTWURF',
            ADD COLUMN IF NOT EXISTS menge       NUMERIC(15,4),
            ADD COLUMN IF NOT EXISTS einheit     VARCHAR(20),
            ADD COLUMN IF NOT EXISTS lagerort    VARCHAR(200),
            ADD COLUMN IF NOT EXISTS notiz       TEXT,
            ADD COLUMN IF NOT EXISTS schritt_protokoll JSONB
    """)

    op.execute("""
        ALTER TABLE prozess_schritte
            ADD COLUMN IF NOT EXISTS objekt_id BIGINT REFERENCES objects(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE prozess_schritte
            ALTER COLUMN item_id DROP NOT NULL
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_objects_stamm_id ON objects(stamm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_objects_obj_status ON objects(obj_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prozess_schritte_objekt_id ON prozess_schritte(objekt_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_prozess_schritte_objekt_id")
    op.execute("DROP INDEX IF EXISTS ix_objects_obj_status")
    op.execute("DROP INDEX IF EXISTS ix_objects_stamm_id")

    op.execute("""
        ALTER TABLE prozess_schritte
            ALTER COLUMN item_id SET NOT NULL
    """)

    op.execute("ALTER TABLE prozess_schritte DROP COLUMN IF EXISTS objekt_id")

    op.execute("""
        ALTER TABLE objects
            DROP COLUMN IF EXISTS stamm_id,
            DROP COLUMN IF EXISTS name,
            DROP COLUMN IF EXISTS obj_status,
            DROP COLUMN IF EXISTS menge,
            DROP COLUMN IF EXISTS einheit,
            DROP COLUMN IF EXISTS lagerort,
            DROP COLUMN IF EXISTS notiz,
            DROP COLUMN IF EXISTS schritt_protokoll
    """)
