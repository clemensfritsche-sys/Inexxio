"""Ausschuss-/Schrott-Lagerort am Unternehmen (Bereitstellungsort «Schrottplatz»).

Verschrottete Instanzen wandern an diesen Lagerort (services/provisioning.py). Fehlt
der Eintrag, legt der Reconciler automatisch einen Lagerplatz «Schrottplatz» an und
hinterlegt dessen Objektnummer hier – analog ``default_receiving_location_id``.

Revision ID: 068
Revises: 067
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '068'
down_revision = '067'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "default_scrap_location_id" not in cols:
            op.add_column("company_settings", sa.Column("default_scrap_location_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("company_settings")}
        if "default_scrap_location_id" in cols:
            op.drop_column("company_settings", "default_scrap_location_id")
