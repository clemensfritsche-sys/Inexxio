"""Beleg-/Dokument-Modul: hochgeladene Fremd-Dokumente (KI-Aufnahme, Reiter «Dokumente»).

Drei Tabellen:
    document_files   – ein hochgeladenes Dokument mit eigener Objektnummer (Titel/Typ/
                       Zusammenfassung/Volltext von der KI; storage_key → GCS oder DB)
    document_links   – n:m-Zuordnung Dokument ↔ ERP-Objekt (Rechnung betrifft mehrere)
    document_blobs   – DB-Fallback für die Bytes, wenn KEIN GCS-Bucket konfiguriert ist

Idempotent (nur anlegen, was fehlt) – ``create_all()`` in der Lifespan ist das Netz,
falls Alembic übersprungen wird.

Revision ID: 059
Revises: 058
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '059'
down_revision = '058'
branch_labels = None
depends_on = None


def _has(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has("document_files"):
        op.create_table(
            "document_files",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("object_id", sa.BigInteger(), nullable=False, unique=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("doc_type", sa.String(30), nullable=False, server_default="other"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("extracted_data", JSONB(), nullable=True),
            sa.Column("mime", sa.String(100), nullable=False, server_default="application/pdf"),
            sa.Column("filename", sa.String(255), nullable=True),
            sa.Column("byte_size", sa.Integer(), nullable=True),
            sa.Column("page_count", sa.Integer(), nullable=True),
            sa.Column("storage_key", sa.String(400), nullable=False),
            sa.Column("storage_backend", sa.String(10), nullable=False, server_default="db"),
            sa.Column("sha256", sa.String(64), nullable=True),
            sa.Column("source", sa.String(10), nullable=False, server_default="upload"),
            sa.Column("ai_model", sa.String(60), nullable=True),
            sa.Column("ai_prompt_version", sa.String(30), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_document_files_object_id", "document_files", ["object_id"], unique=True)
        op.create_index("ix_document_files_sha256", "document_files", ["sha256"])

    if not _has("document_links"):
        op.create_table(
            "document_links",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("document_id", sa.BigInteger(), nullable=False),
            sa.Column("object_id", sa.BigInteger(), nullable=False),
            sa.Column("object_type", sa.String(30), nullable=True),
            sa.Column("relation", sa.String(30), nullable=False, server_default="about"),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_document_links_document_id", "document_links", ["document_id"])
        op.create_index("ix_document_links_object_id", "document_links", ["object_id"])

    if not _has("document_blobs"):
        op.create_table(
            "document_blobs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("storage_key", sa.String(400), nullable=False, unique=True),
            sa.Column("mime", sa.String(100), nullable=False, server_default="application/octet-stream"),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("byte_size", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_document_blobs_storage_key", "document_blobs", ["storage_key"], unique=True)


def downgrade() -> None:
    for t in ("document_links", "document_blobs", "document_files"):
        if _has(t):
            op.drop_table(t)
