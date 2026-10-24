"""Die Mail, wie sie hinausging, und «in Gmail gelesen».

``messages.html`` hält die gebaute Mail (``services/mail_layout``), ``messages.read_marked``
sagt, dass eine erledigte Nachricht in Gmail schon als gelesen markiert ist. Beide stehen
auch im ``_COLUMN_SAFETY_NET``.
"""
from alembic import op

revision = "150"
down_revision = "149"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS html TEXT")
    op.execute("ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_marked "
               "BOOLEAN NOT NULL DEFAULT false")


def downgrade() -> None:
    op.drop_column("messages", "read_marked")
    op.drop_column("messages", "html")
