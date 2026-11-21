"""Gmail meldet neue Mails selbst (Push über Pub/Sub): bis wann die Anmeldung gilt.

``mailboxes.watch_until`` – Gmail nimmt eine Anmeldung (``users.watch``) für höchstens sieben
Tage an; der Takt erneuert sie, bevor sie abläuft. Leer = ohne Push (der Takt holt ab).

Revision ID: 185
Revises: 184
"""

from alembic import op

revision = "185"
down_revision = "184"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE mailboxes ADD COLUMN watch_until timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE mailboxes DROP COLUMN IF EXISTS watch_until")
