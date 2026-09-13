"""Seller of Record je Verkauf: ``sales.seller_company_object_id`` (ADR 006, Slice 2).

Die **fakturierende Gesellschaft** je Verkaufsbeleg – abgeleitet aus der Rechnungsadresse des
Kunden (``sites.company_for_country``) und bei der Zahlung eingefroren (Snapshot), damit der
Beleg unveränderlich die richtige Rechtsperson trägt. NULL bei Alt-Belegen → Fallback Betreiber.

Neue **Spalte auf bestehender Tabelle** – steht daher auch im Lifespan-Safety-Net
(``main._COLUMN_SAFETY_NET``): läuft die Migration nicht, zieht das Netz die Spalte nach; sonst
endete jede ``sales``-Abfrage in einem 500 (die Lehre aus Migration 090). **Idempotent**.

Revision ID: 093
Revises: 092
"""

from alembic import op
import sqlalchemy as sa

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def _cols(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("sales")}


def upgrade() -> None:
    conn = op.get_bind()
    if "seller_company_object_id" not in _cols(conn):
        op.add_column("sales", sa.Column("seller_company_object_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if "seller_company_object_id" in _cols(conn):
        op.drop_column("sales", "seller_company_object_id")
