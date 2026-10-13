"""Kommunikation: die Nachricht als einziges Objekt (CRM Schritt 2).

* ``messages`` – Absender, Kanal (Katalog ``domain/communication``), Betreff, Text,
  Zeitpunkt; keine Objektnummer, kein Status.
* ``message_parties`` – An · Cc · Bcc · Betrifft.
* ``message_replies`` – «Antwort auf» als Liste.

Neue Tabellen legt auf dev ``create_all`` an; hier stehen sie, weil die Migration die
Wahrheit ist. Idempotent je Tabelle.
"""
import sqlalchemy as sa
from alembic import op

revision = "144"
down_revision = "143"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    have = _tables()
    if "messages" not in have:
        op.create_table(
            "messages",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("sender_object_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("channel", sa.String(20), nullable=False),
            sa.Column("subject", sa.String(255)),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("created_by", sa.BigInteger()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
        )
    if "message_parties" not in have:
        op.create_table(
            "message_parties",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("messages.id"),
                      nullable=False, index=True),
            sa.Column("person_object_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("role", sa.String(5), nullable=False),
        )
    if "message_replies" not in have:
        op.create_table(
            "message_replies",
            sa.Column("message_id", sa.BigInteger(), sa.ForeignKey("messages.id"),
                      primary_key=True),
            sa.Column("reply_to_id", sa.BigInteger(), sa.ForeignKey("messages.id"),
                      primary_key=True, index=True),
        )


def downgrade() -> None:
    for t in ("message_replies", "message_parties", "messages"):
        if t in _tables():
            op.drop_table(t)
