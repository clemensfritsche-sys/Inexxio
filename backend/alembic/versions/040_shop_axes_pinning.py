"""Shop-Optimierung: Verfügbarkeits-Achse (make/stock), explizite Subjekt-Quelle,
gepinnte Fremdwährungspreise und optionale Zonen-Faktoren.

- ``articles.sales_fulfillment`` (make = Made-to-Order | stock = ab Lager/FIFO).
- ``orders.subject_source`` (produce|stock überschreibt die Ableitung – Shop-Made-to-Order).
- ``article_prices.pinned`` (gepinnte Fremdwährungspreise statt Live-Umrechnung).
- ``company_settings.pricing_zone_factors`` (optionale PPP-Stufe, Default aus).

Revision ID: 040
Revises: 039
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '040'
down_revision = '039'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())

    if not _has_col(insp, "articles", "sales_fulfillment"):
        op.add_column("articles", sa.Column("sales_fulfillment", sa.String(length=10),
                                            nullable=False, server_default="make"))
    if not _has_col(insp, "orders", "subject_source"):
        op.add_column("orders", sa.Column("subject_source", sa.String(length=10), nullable=True))
    if not _has_col(insp, "article_prices", "pinned"):
        op.add_column("article_prices", sa.Column("pinned", postgresql.JSONB(), nullable=True))
    if not _has_col(insp, "company_settings", "pricing_zone_factors"):
        op.add_column("company_settings", sa.Column("pricing_zone_factors", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("company_settings", "pricing_zone_factors")
    op.drop_column("article_prices", "pinned")
    op.drop_column("orders", "subject_source")
    op.drop_column("articles", "sales_fulfillment")
