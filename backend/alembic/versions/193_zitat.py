"""Das Zitat einer Mail (``messages.quote``): was unter dem Text stand – bei einer Weiterleitung die
eigentliche Sache. Beim Abholen mitgespeichert (``mail_parse.text_and_quote``), zugeklappt an der
Mail, die KI liest es mit. Bisher fiel es weg. Inhaber 28.11.2026.

Revision ID: 193
Revises: 192
"""

from alembic import op

revision = "193"
down_revision = "192"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN quote TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS quote")
