"""Aussortierte Anfragen der Website (``services/spam``): je aussortierter Anfrage genau ein
Entscheid – «Kein Spam» (``inquiry.released``) oder «Spam» (``inquiry.discarded``). Ein zweiter
Klick, gleichzeitig an zwei Bildschirmen, scheitert am Index, nicht an der Hoffnung.

Revision ID: 192
Revises: 191
"""

from alembic import op

revision = "192"
down_revision = "191"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX ix_log_inquiry_decided ON log "
               "(((payload ->> 'held')::bigint)) "
               "WHERE event IN ('inquiry.released', 'inquiry.discarded')")
    op.execute("CREATE INDEX ix_log_inquiry_held ON log (object_id, at) "
               "WHERE event = 'inquiry.held'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_inquiry_held")
    op.execute("DROP INDEX IF EXISTS ix_log_inquiry_decided")
