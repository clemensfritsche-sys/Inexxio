"""Logistik/Versand (ADR 005): «Versand wird abgeleitet, nicht bestellt».

- ``shipments``: Versand-Beleg je Bewegungs-Schritt (Rate-Shopping-Snapshot,
  Label, Tracking; keine eigene Objektnummer – analog movements/purchase_orders).
- ``articles.is_hazmat``: Gefahrgut als optionales Spezifikationsfeld.
- ``company_settings.site_latitude/longitude/radius_m``: Betriebs-Geofence –
  Bewegungs-Ziel ausserhalb → externer Transport.
- ``article_process_steps.transport_mode``: deklarierter Transport-Modus der
  Bewegung (auto | carrier | self | none).

Revision ID: 071
Revises: 070
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '071'
down_revision = '070'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()

    if "shipments" not in tables:
        op.create_table(
            "shipments",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("order_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("step_id", sa.BigInteger(), nullable=True, index=True),
            sa.Column("direction", sa.String(10), nullable=False, server_default="outbound"),
            sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
            sa.Column("provider", sa.String(12), nullable=False, server_default="manual"),
            sa.Column("transport_mode", sa.String(10), nullable=True),
            sa.Column("address_from", JSONB(), nullable=True),
            sa.Column("address_to", JSONB(), nullable=True),
            sa.Column("parcels", JSONB(), nullable=True),
            sa.Column("hazmat", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("rates", JSONB(), nullable=True),
            sa.Column("chosen_rate_id", sa.String(64), nullable=True),
            sa.Column("carrier", sa.String(60), nullable=True),
            sa.Column("service", sa.String(120), nullable=True),
            sa.Column("label_url", sa.String(500), nullable=True),
            sa.Column("tracking_number", sa.String(100), nullable=True),
            sa.Column("tracking_url", sa.String(500), nullable=True),
            sa.Column("cost_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("cost_currency", sa.String(3), nullable=True),
            sa.Column("provider_shipment_id", sa.String(64), nullable=True),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
        op.create_index("ix_shipments_step_id", "shipments", ["step_id"])

    def add_col(table: str, col: sa.Column) -> None:
        if table in tables:
            cols = {c["name"] for c in insp.get_columns(table)}
            if col.name not in cols:
                op.add_column(table, col)

    add_col("articles", sa.Column("is_hazmat", sa.Boolean(), nullable=False, server_default="false"))
    add_col("company_settings", sa.Column("site_latitude", sa.Numeric(9, 6), nullable=True))
    add_col("company_settings", sa.Column("site_longitude", sa.Numeric(9, 6), nullable=True))
    add_col("company_settings", sa.Column("site_radius_m", sa.Integer(), nullable=True))
    add_col("article_process_steps", sa.Column("transport_mode", sa.String(10), nullable=False, server_default="auto"))


def downgrade() -> None:
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()
    if "shipments" in tables:
        op.drop_table("shipments")

    def drop_col(table: str, name: str) -> None:
        if table in tables:
            cols = {c["name"] for c in insp.get_columns(table)}
            if name in cols:
                op.drop_column(table, name)

    drop_col("articles", "is_hazmat")
    drop_col("company_settings", "site_latitude")
    drop_col("company_settings", "site_longitude")
    drop_col("company_settings", "site_radius_m")
    drop_col("article_process_steps", "transport_mode")
