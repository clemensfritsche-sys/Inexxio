"""Prozessschrittmodul «Dokument» + nicht-physische Artikel.

Neu:
  • ``articles.physical`` (bool, default true) – trennt physische Güter von nicht-physischen
    (Dokument; später Software). Ein nicht-physischer Artikel erzeugt bei der Auftragsfreigabe
    KEINE Bestands-Instanzen; sein Liefergegenstand ist das nummerierte Dokument.
  • ``article_process_steps.document_content`` (JSONB) – die editierbare Dokument-Vorlage am
    Prozessschritt (Titel/Untertitel/Abschnitte). Einfrieren bei der Freigabe.
  • Tabelle ``documents`` – das erzeugte, nummerierte, unveränderliche Dokument (Fachzeile des
    ``document``-Schritts). Trägt – wie eine Instanz – eine eigene Objektnummer.

Revision ID: 050
Revises: 049
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '050'
down_revision = '049'
branch_labels = None
depends_on = None


def _has_column(insp, table, col) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "articles" in insp.get_table_names() and not _has_column(insp, "articles", "physical"):
        op.add_column("articles", sa.Column(
            "physical", sa.Boolean(), nullable=False, server_default=sa.true()))

    if not _has_column(insp, "article_process_steps", "document_content"):
        op.add_column("article_process_steps", sa.Column(
            "document_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    if "documents" not in insp.get_table_names():
        op.create_table(
            "documents",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("object_id", sa.BigInteger(), nullable=True),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("step_id", sa.BigInteger(), nullable=True),
            sa.Column("article_id", sa.BigInteger(), nullable=True),
            sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("replaced_by_id", sa.BigInteger(), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.create_index("ix_documents_object_id", "documents", ["object_id"], unique=True)
        op.create_index("ix_documents_order_id", "documents", ["order_id"])
        op.create_index("ix_documents_step_id", "documents", ["step_id"])
        op.create_index("ix_documents_article_id", "documents", ["article_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "documents" in insp.get_table_names():
        op.drop_table("documents")
    if _has_column(insp, "article_process_steps", "document_content"):
        op.drop_column("article_process_steps", "document_content")
    if _has_column(insp, "articles", "physical"):
        op.drop_column("articles", "physical")
