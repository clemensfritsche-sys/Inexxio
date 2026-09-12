"""Verkaufs-/Shop-Modul: Verkaufs-Ebene am Artikel, Preise, Zielgruppe, FX-Kurse,
Snapshot am Verkaufsbeleg und Shop-Konfiguration.

Der Verkauf lebt AM ARTIKEL (dritte, bewusst lebende Ebene – kein eigenes Objekt):
``articles.sales_*`` + 1:n ``article_prices`` + ``article_sales_audience``. Beim Kauf
friert der ``sale``-Beleg Preis/Währung/FX/Steuer ein (``sales.base_amount_chf`` …).
``fx_rates`` ist die unveränderliche Tageshistorie der Wechselkurse.

Revision ID: 039
Revises: 038
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None


def _has_col(insp, table: str, col: str) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())

    # ── articles: Verkaufs-Ebene (nicht von der Freigabe eingefroren) ─────────────
    if not _has_col(insp, "articles", "sales_published"):
        op.add_column("articles", sa.Column("sales_published", sa.Boolean(), nullable=False,
                                            server_default=sa.false()))
    if not _has_col(insp, "articles", "sales_visibility"):
        op.add_column("articles", sa.Column("sales_visibility", sa.String(length=10), nullable=False,
                                            server_default="public"))
    if not _has_col(insp, "articles", "sales_content"):
        op.add_column("articles", sa.Column("sales_content", postgresql.JSONB(), nullable=True))

    # ── article_prices ────────────────────────────────────────────────────────────
    if not insp.has_table("article_prices"):
        op.create_table(
            "article_prices",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("article_id", sa.BigInteger(), nullable=False),
            sa.Column("kind", sa.String(length=12), nullable=False, server_default="one_time"),
            sa.Column("interval", sa.String(length=8), nullable=True),
            sa.Column("amount_chf", sa.Numeric(12, 2), nullable=False),
            sa.Column("compare_at_chf", sa.Numeric(12, 2), nullable=True),
            sa.Column("tax_class", sa.String(length=16), nullable=False, server_default="standard"),
            sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_article_prices_article_id", "article_prices", ["article_id"])

    # ── article_sales_audience ────────────────────────────────────────────────────
    if not insp.has_table("article_sales_audience"):
        op.create_table(
            "article_sales_audience",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("article_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_article_sales_audience_article_id", "article_sales_audience", ["article_id"])
        op.create_index("ix_article_sales_audience_user_id", "article_sales_audience", ["user_id"])

    # ── fx_rates (unveränderliche Tageshistorie) ──────────────────────────────────
    if not insp.has_table("fx_rates"):
        op.create_table(
            "fx_rates",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("rate_to_chf", sa.Numeric(18, 8), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=True),
            sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("day", "currency", name="uq_fx_rates_day_currency"),
        )
        op.create_index("ix_fx_rates_day", "fx_rates", ["day"])

    # ── sales: Snapshot beim Kauf ─────────────────────────────────────────────────
    for col, type_ in (
        ("base_amount_chf", sa.Numeric(12, 2)),
        ("fx_rate", sa.Numeric(18, 8)),
        ("fx_date", sa.Date()),
        ("tax_class", sa.String(length=16)),
    ):
        if not _has_col(insp, "sales", col):
            op.add_column("sales", sa.Column(col, type_, nullable=True))

    # ── company_settings: Shop-Konfiguration ──────────────────────────────────────
    if not _has_col(insp, "company_settings", "shop_currencies"):
        op.add_column("company_settings", sa.Column("shop_currencies", postgresql.JSONB(), nullable=True))
    if not _has_col(insp, "company_settings", "shop_country_currency"):
        op.add_column("company_settings", sa.Column("shop_country_currency", postgresql.JSONB(), nullable=True))
    if not _has_col(insp, "company_settings", "shop_default_currency"):
        op.add_column("company_settings", sa.Column("shop_default_currency", sa.String(length=3),
                                                    nullable=False, server_default="CHF"))
    if not _has_col(insp, "company_settings", "payments_provider"):
        op.add_column("company_settings", sa.Column("payments_provider", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("company_settings", "payments_provider")
    op.drop_column("company_settings", "shop_default_currency")
    op.drop_column("company_settings", "shop_country_currency")
    op.drop_column("company_settings", "shop_currencies")
    for col in ("tax_class", "fx_date", "fx_rate", "base_amount_chf"):
        op.drop_column("sales", col)
    op.drop_table("fx_rates")
    op.drop_table("article_sales_audience")
    op.drop_table("article_prices")
    op.drop_column("articles", "sales_content")
    op.drop_column("articles", "sales_visibility")
    op.drop_column("articles", "sales_published")
