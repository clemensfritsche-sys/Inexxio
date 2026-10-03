"""Öffentliche Rechtsdokumente – Zeiger am Unternehmen (D).

Ein Rechtsdokument (AGB/Datenschutz/…) ist append-only: jede Fassung ist eine eigene,
unveränderliche Dokument-Instanz. Welche gerade GILT, ist ein Zeiger am Unternehmen:
    legal_documents (JSONB) = {"agb": 100000123, "datenschutz": 100000124, …}
Wert = Objektnummer der gültigen Dokument-Instanz. Alte Fassungen bleiben archiviert.

Revision ID: 057
Revises: 056
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '057'
down_revision = '056'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("company_settings")}
    if "legal_documents" not in have:
        op.add_column("company_settings", sa.Column("legal_documents", JSONB(), nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("company_settings")}
    if "legal_documents" in have:
        op.drop_column("company_settings", "legal_documents")
