"""Das Bild des Postfachs – es steht neben der Unterschrift jeder Mail.

Revision ID: 151
Revises: 150
"""

from alembic import op

revision = "151"
down_revision = "150"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE mailboxes ADD COLUMN IF NOT EXISTS picture TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE mailboxes DROP COLUMN IF EXISTS picture")
