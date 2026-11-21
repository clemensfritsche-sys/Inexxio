"""MCP: eine Erneuerung gilt genau einmal (``services/mcp._refresh``).

* ``ix_log_mcp_refresh``: **eindeutig** je Einmal-Nummer einer Erneuerung – kommt sie ein zweites
  Mal, wird die Verbindung getrennt.

Revision ID: 180
Revises: 179
"""

from alembic import op

revision = "180"
down_revision = "179"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_log_mcp_refresh ON log ((payload ->> 'nonce')) "
               "WHERE event = 'mcp.refresh'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_mcp_refresh")
