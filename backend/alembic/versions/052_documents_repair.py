"""documents-Tabelle sauber neu aufbauen (Reparatur eines inkonsistenten Dev-Stands).

Auf dem Dev-Stand ist die ``documents``-Tabelle nach der Migrations-/create_all-Historie
inkonsistent (u. a. fehlt ``order_id``), sodass das neue Modell beim Lesen scheitert
(``column documents.order_id does not exist``). Der Inhalt sind ausschliesslich Wegwerf-
Testdaten des frisch eingeführten Moduls, daher wird die Tabelle **idempotent neu aufgebaut**
und exakt an das aktuelle Modell (``models/document.py``) angeglichen.

Revision ID: 052
Revises: 051
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '052'
down_revision = '051'
branch_labels = None
depends_on = None


def _create_documents() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("step_id", sa.BigInteger(), nullable=True),
        sa.Column("article_id", sa.BigInteger(), nullable=True),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_documents_order_id", "documents", ["order_id"])
    op.create_index("ix_documents_step_id", "documents", ["step_id"])
    op.create_index("ix_documents_article_id", "documents", ["article_id"])


def upgrade() -> None:
    # Keine Fremdschlüssel zeigen auf documents → sauberes DROP/CREATE (idempotent).
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    _create_documents()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    _create_documents()
