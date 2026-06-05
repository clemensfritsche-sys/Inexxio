"""Item type overhaul: new fields, status workflow, lookup tables, signatures

Revision ID: 007
Revises: 006
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── item_names ────────────────────────────────────────────────────────────
    op.create_table(
        "item_names",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_item_names_label", "item_names", ["label"])

    # ── item_surfaces ─────────────────────────────────────────────────────────
    op.create_table(
        "item_surfaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_item_surfaces_label", "item_surfaces", ["label"])

    # ── item_categories ───────────────────────────────────────────────────────
    op.create_table(
        "item_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("label"),
    )
    op.create_index("ix_item_categories_label", "item_categories", ["label"])

    # ── items: drop obsolete columns ──────────────────────────────────────────
    op.drop_index("ix_items_category", table_name="items")
    op.drop_column("items", "description")
    op.drop_column("items", "size")
    op.drop_column("items", "category")
    op.drop_column("items", "is_equipment")
    op.drop_column("items", "serial_mode")
    op.drop_column("items", "shop_description")
    op.drop_column("items", "purchase_type")
    op.drop_column("items", "list_price_chf")
    op.drop_column("items", "min_stock")
    op.drop_column("items", "reorder_point")
    op.drop_column("items", "max_stock")
    op.drop_column("items", "preferred_supplier_id")
    op.drop_column("items", "is_approved")
    op.drop_column("items", "current_stock")

    # ── items: add new columns ────────────────────────────────────────────────
    op.add_column("items", sa.Column("name_id", sa.Integer(), sa.ForeignKey("item_names.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("items", sa.Column("status", sa.String(20), nullable=False, server_default="ENTWURF"))
    op.add_column("items", sa.Column("batch_allowed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("items", sa.Column("order_number", sa.String(100), nullable=True))
    op.add_column("items", sa.Column("order_link", sa.String(500), nullable=True))
    op.add_column("items", sa.Column("onshape_link", sa.String(500), nullable=True))
    op.add_column("items", sa.Column("weight_g", sa.Numeric(12, 4), nullable=True))
    op.add_column("items", sa.Column("dim_1_mm", sa.Numeric(12, 4), nullable=True))
    op.add_column("items", sa.Column("dim_2_mm", sa.Numeric(12, 4), nullable=True))
    op.add_column("items", sa.Column("dim_3_mm", sa.Numeric(12, 4), nullable=True))
    op.add_column("items", sa.Column("surface_id", sa.Integer(), sa.ForeignKey("item_surfaces.id", ondelete="SET NULL"), nullable=True))
    op.add_column("items", sa.Column("purchase_price", sa.Numeric(15, 4), nullable=True))
    op.add_column("items", sa.Column("purchase_currency", sa.String(3), nullable=False, server_default="CHF"))
    op.add_column("items", sa.Column("stock_total", sa.Numeric(15, 3), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("stock_reserved", sa.Numeric(15, 3), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("sales_price", sa.Numeric(15, 4), nullable=True))
    op.add_column("items", sa.Column("sales_currency", sa.String(3), nullable=False, server_default="CHF"))
    op.add_column("items", sa.Column("category_id", sa.Integer(), sa.ForeignKey("item_categories.id", ondelete="SET NULL"), nullable=True))
    op.add_column("items", sa.Column("vat_rate", sa.String(5), nullable=True))
    op.add_column("items", sa.Column("shop_description_long", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("seo_title", sa.String(200), nullable=True))
    op.add_column("items", sa.Column("seo_description", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("items", sa.Column("submitted_by", sa.BigInteger(), nullable=True))
    op.create_index("ix_items_status", "items", ["status"])

    # ── item_signatures ───────────────────────────────────────────────────────
    op.create_table(
        "item_signatures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "signed_by",
            sa.BigInteger(),
            sa.ForeignKey("user_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "signed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_item_signatures_item_id", "item_signatures", ["item_id"])


def downgrade() -> None:
    op.drop_table("item_signatures")

    op.drop_index("ix_items_status", table_name="items")
    op.drop_column("items", "submitted_by")
    op.drop_column("items", "submitted_at")
    op.drop_column("items", "seo_description")
    op.drop_column("items", "seo_title")
    op.drop_column("items", "shop_description_long")
    op.drop_column("items", "vat_rate")
    op.drop_column("items", "category_id")
    op.drop_column("items", "sales_currency")
    op.drop_column("items", "sales_price")
    op.drop_column("items", "stock_reserved")
    op.drop_column("items", "stock_total")
    op.drop_column("items", "purchase_currency")
    op.drop_column("items", "purchase_price")
    op.drop_column("items", "surface_id")
    op.drop_column("items", "dim_3_mm")
    op.drop_column("items", "dim_2_mm")
    op.drop_column("items", "dim_1_mm")
    op.drop_column("items", "weight_g")
    op.drop_column("items", "onshape_link")
    op.drop_column("items", "order_link")
    op.drop_column("items", "order_number")
    op.drop_column("items", "batch_allowed")
    op.drop_column("items", "status")
    op.drop_column("items", "name_id")

    op.add_column("items", sa.Column("current_stock", sa.Numeric(15, 3), nullable=False, server_default="0"))
    op.add_column("items", sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("items", sa.Column("preferred_supplier_id", sa.BigInteger(), nullable=True))
    op.add_column("items", sa.Column("max_stock", sa.Numeric(15, 3), nullable=True))
    op.add_column("items", sa.Column("reorder_point", sa.Numeric(15, 3), nullable=True))
    op.add_column("items", sa.Column("min_stock", sa.Numeric(15, 3), nullable=True))
    op.add_column("items", sa.Column("list_price_chf", sa.Numeric(15, 4), nullable=True))
    op.add_column("items", sa.Column("purchase_type", sa.String(20), nullable=False, server_default="one_time"))
    op.add_column("items", sa.Column("shop_description", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("serial_mode", sa.String(20), nullable=False, server_default="unit"))
    op.add_column("items", sa.Column("is_equipment", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("items", sa.Column("category", sa.String(100), nullable=True))
    op.add_column("items", sa.Column("size", sa.String(100), nullable=True))
    op.add_column("items", sa.Column("description", sa.Text(), nullable=True))
    op.create_index("ix_items_category", "items", ["category"])

    op.drop_index("ix_item_categories_label", table_name="item_categories")
    op.drop_table("item_categories")
    op.drop_index("ix_item_surfaces_label", table_name="item_surfaces")
    op.drop_table("item_surfaces")
    op.drop_index("ix_item_names_label", table_name="item_names")
    op.drop_table("item_names")
