"""Consent-Gate: document_acknowledgements + company_settings.legal_ack_config.

* Tabelle ``document_acknowledgements`` – wer welche Version (Objektnummer der Dokument-
  Instanz) welcher Dokument-Art wann bestätigt hat (append-only, Nachweis).
* Spalte ``company_settings.legal_ack_config`` (JSONB) – welche Arten von welchen Rollen
  bestätigt werden müssen (``{"agb": ["all"]}``).

Revision ID: 064
Revises: 063
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '064'
down_revision = '063'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "document_acknowledgements" not in insp.get_table_names():
        op.create_table(
            "document_acknowledgements",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("version_object_id", sa.BigInteger(), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_document_acknowledgements_user_id", "document_acknowledgements", ["user_id"])
        op.create_index("ix_document_acknowledgements_kind", "document_acknowledgements", ["kind"])

    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "legal_ack_config" not in cols:
            op.add_column("company_settings", sa.Column("legal_ack_config", JSONB(), nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "legal_ack_config" in cols:
            op.drop_column("company_settings", "legal_ack_config")
    if "document_acknowledgements" in insp.get_table_names():
        op.drop_table("document_acknowledgements")
