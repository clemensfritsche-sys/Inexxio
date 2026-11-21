"""Der Schlüssel eines Wischs gilt je Person.

``uq_time_entries_key`` war über alle Personen eindeutig: derselbe Schlüssel zweier Personen
liess den Wisch der zweiten still fallen (``timekeeping.swipe`` fand ihn bei der ersten). Ein
Wisch ist derselbe nur bei derselben Person – der Index nennt beide.

Revision ID: 187
Revises: 186
"""

from alembic import op

revision = "187"
down_revision = "186"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_time_entries_key")
    op.execute("CREATE UNIQUE INDEX uq_time_entries_key ON time_entries "
               "(person_object_id, idem_key) WHERE idem_key IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_time_entries_key")
    op.execute("CREATE UNIQUE INDEX uq_time_entries_key ON time_entries (idem_key) "
               "WHERE idem_key IS NOT NULL")
