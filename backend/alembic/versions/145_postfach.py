"""Postfach: Gmail-Anbindung (CRM Schritt 3).

* ``mailboxes`` – je Kanal höchstens ein verbundenes Postfach (Token verschlüsselt).
* ``messages`` + ``gmail_id`` · ``thread_id`` · ``rfc_id`` · ``outgoing`` ·
  ``attachments`` – die Mail bleibt in Gmail, hier steht der Weg dorthin.

Idempotent je Objekt; auf dev ziehen ``create_all`` (Tabelle), das Spalten-Netz und das
Roh-Index-Netz dasselbe nach.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "145"
down_revision = "144"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("gmail_id", sa.String(64)),
    ("thread_id", sa.String(64)),
    ("rfc_id", sa.String(255)),
    ("outgoing", sa.Boolean()),
    ("attachments", JSONB()),
)


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if "mailboxes" not in insp.get_table_names():
        op.create_table(
            "mailboxes",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("address", sa.String(255), nullable=False),
            sa.Column("owner_object_id", sa.BigInteger(), nullable=False),
            sa.Column("token", sa.Text(), nullable=False),
            sa.Column("history_id", sa.String(32)),
            sa.Column("problem", sa.Text()),
            sa.Column("synced_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        )
    have = {c["name"] for c in insp.get_columns("messages")}
    for name, typ in _COLUMNS:
        if name not in have:
            if name == "outgoing":
                op.add_column("messages", sa.Column(name, typ, nullable=False,
                                                    server_default="false"))
            else:
                op.add_column("messages", sa.Column(name, typ))
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_mailboxes_channel "
               "ON mailboxes (channel) WHERE is_active")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_rfc_id "
               "ON messages (rfc_id) WHERE rfc_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_messages_gmail "
               "ON messages (channel, gmail_id) WHERE gmail_id IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_messages_gmail")
    op.execute("DROP INDEX IF EXISTS uq_messages_rfc_id")
    for name, _ in _COLUMNS:
        op.execute(f"ALTER TABLE messages DROP COLUMN IF EXISTS {name}")
    op.execute("DROP TABLE IF EXISTS mailboxes")
