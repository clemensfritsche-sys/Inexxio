"""MCP: eine Verbindung mit Claude ist ein Ereignis im Log (``services/mcp``).

* ``ix_log_mcp_grant``: **eindeutig** je Einmal-Nummer des Codes – ein Code lässt sich genau
  einmal gegen Zugang tauschen.
* ``ix_log_mcp_revoked``: «ist diese Verbindung getrennt?» fragt jede Anfrage.

Revision ID: 179
Revises: 178
"""

from alembic import op

revision = "179"
down_revision = "178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_log_mcp_grant ON log ((payload ->> 'nonce')) "
               "WHERE event = 'mcp.grant'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_log_mcp_revoked ON log "
               "(((payload ->> 'grant')::bigint)) WHERE event = 'mcp.revoked'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_mcp_revoked")
    op.execute("DROP INDEX IF EXISTS ix_log_mcp_grant")
