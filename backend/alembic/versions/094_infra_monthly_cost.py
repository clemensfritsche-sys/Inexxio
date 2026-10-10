"""Konfigurierbare Infrastruktur-Kosten/Monat: ``company_settings.infra_monthly_chf`` (Notiz #293).

Der reale, fixe Google-Cloud-Monatsbetrag aus der Abrechnung. Ist er gesetzt, zeigt die
Betriebskosten-Übersicht ihn als **fix** statt geschätzt. Plattform-Feld (nur Betreiber, über
die Systemkonfiguration).

Neue **Spalte auf bestehender Tabelle** → steht auch im Lifespan-Safety-Net
(``main._COLUMN_SAFETY_NET``, 090-Lehre). **Idempotent**.

Revision ID: 094
Revises: 093
"""

from alembic import op
import sqlalchemy as sa

revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None


def _cols(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("company_settings")}


def upgrade() -> None:
    conn = op.get_bind()
    if "infra_monthly_chf" not in _cols(conn):
        op.add_column("company_settings", sa.Column("infra_monthly_chf", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if "infra_monthly_chf" in _cols(conn):
        op.drop_column("company_settings", "infra_monthly_chf")
