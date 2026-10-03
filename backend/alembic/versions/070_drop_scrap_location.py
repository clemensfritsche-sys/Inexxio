"""Schrott-Lagerort entfernen – verschrottete Instanzen sind standortlos.

Kehrt Migration 068 um: eine verschrottete Instanz (``disposition='scrapped'``) hat
KEINEN Standort mehr (ein Standort ist immer ein realer Halter – Lagerplatz/Person/
Instanz –, den Ausschuss nicht hat). Der Bereitstellungsort «Schrottplatz» entfällt;
``services/scrap.py`` macht die ganz verschrottete Instanz über ``location_split.clear``
standortlos. Damit ist ``company_settings.default_scrap_location_id`` überflüssig.

Revision ID: 070
Revises: 069
Create Date: 2026-07-09
"""
from alembic import op
from sqlalchemy import inspect

revision = '070'
down_revision = '069'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "default_scrap_location_id" in cols:
            op.drop_column("company_settings", "default_scrap_location_id")


def downgrade() -> None:
    import sqlalchemy as sa
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "default_scrap_location_id" not in cols:
            op.add_column("company_settings", sa.Column("default_scrap_location_id", sa.BigInteger(), nullable=True))
