"""Tote Konfiguration entfernen: ``company_settings.legal_ack_config``.

Die Spalte war als konfigurierbare Bestätigungspflicht gedacht, wurde aber nie
ausgewertet (Review 2026-07): die Pflicht ist hart verdrahtet
(``consent.MUST_ACKNOWLEDGE_KINDS``), Rollen-/Personen-Publikum läuft über die
Dokument-Schritte (``doc_audience``).

Revision ID: 075
Revises: 074
Create Date: 2026-07-14
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '075'
down_revision = '074'
branch_labels = None
depends_on = None


def _has_column(insp, table: str, column: str) -> bool:
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names() and _has_column(insp, "company_settings", "legal_ack_config"):
        op.drop_column("company_settings", "legal_ack_config")


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "company_settings" in insp.get_table_names() and not _has_column(insp, "company_settings", "legal_ack_config"):
        op.add_column("company_settings", sa.Column("legal_ack_config", JSONB, nullable=True))
