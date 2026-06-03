"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Sequence for universal object IDs ────────────────────────────────────
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS object_id_seq "
        "START WITH 100000001 INCREMENT BY 1 NO CYCLE"
    )

    # ── objects ───────────────────────────────────────────────────────────────
    op.create_table(
        "objects",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Sequence("object_id_seq"),
            server_default=sa.text("nextval('object_id_seq')"),
            nullable=False,
        ),
        sa.Column("object_type", sa.String(50), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_objects_object_type", "objects", ["object_type"])

    # ── user_profiles ─────────────────────────────────────────────────────────
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="de"),
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default="Europe/Zurich",
        ),
        sa.Column("weekly_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "notification_email", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "notification_inapp", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_version", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_user_profiles_firebase_uid", "user_profiles", ["firebase_uid"])
    op.create_index("ix_user_profiles_email", "user_profiles", ["email"])

    # ── items ─────────────────────────────────────────────────────────────────
    op.create_table(
        "items",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.ForeignKey("objects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(50), nullable=False, server_default="Stk"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_equipment", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("serial_mode", sa.String(20), nullable=False, server_default="unit"),
        sa.Column("replaced_by_id", sa.BigInteger(), sa.ForeignKey("items.id"), nullable=True),
        sa.Column("replaces_id", sa.BigInteger(), sa.ForeignKey("items.id"), nullable=True),
        sa.Column(
            "is_sales_product", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("shop_description", sa.Text(), nullable=True),
        sa.Column(
            "purchase_type", sa.String(20), nullable=False, server_default="one_time"
        ),
        sa.Column("list_price_chf", sa.Numeric(15, 4), nullable=True),
        sa.Column("hs_code", sa.String(20), nullable=True),
        sa.Column("min_stock", sa.Numeric(15, 3), nullable=True),
        sa.Column("reorder_point", sa.Numeric(15, 3), nullable=True),
        sa.Column("max_stock", sa.Numeric(15, 3), nullable=True),
        sa.Column("preferred_supplier_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "current_stock", sa.Numeric(15, 3), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_name", "items", ["name"])
    op.create_index("ix_items_category", "items", ["category"])

    # ── boms ──────────────────────────────────────────────────────────────────
    op.create_table(
        "boms",
        sa.Column(
            "id", sa.BigInteger(), sa.ForeignKey("objects.id"), nullable=False
        ),
        sa.Column(
            "parent_item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_boms_parent_item_id", "boms", ["parent_item_id"])

    # ── bom_lines ─────────────────────────────────────────────────────────────
    op.create_table(
        "bom_lines",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "bom_id",
            sa.BigInteger(),
            sa.ForeignKey("boms.id"),
            nullable=False,
        ),
        sa.Column(
            "component_item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False, server_default="Stk"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_lines_bom_id", "bom_lines", ["bom_id"])

    # ── work_plans ────────────────────────────────────────────────────────────
    op.create_table(
        "work_plans",
        sa.Column(
            "id", sa.BigInteger(), sa.ForeignKey("objects.id"), nullable=False
        ),
        sa.Column(
            "item_id",
            sa.BigInteger(),
            sa.ForeignKey("items.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── work_plan_steps ───────────────────────────────────────────────────────
    op.create_table(
        "work_plan_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "work_plan_id",
            sa.BigInteger(),
            sa.ForeignKey("work_plans.id"),
            nullable=False,
        ),
        sa.Column("step_nr", sa.Integer(), nullable=False),
        sa.Column(
            "step_type", sa.String(20), nullable=False, server_default="operation"
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("resource", sa.String(255), nullable=True),
        sa.Column("setup_min", sa.Numeric(8, 2), nullable=True),
        sa.Column("exec_min_per_unit", sa.Numeric(8, 2), nullable=True),
        sa.Column("nominal_value", sa.Numeric(15, 4), nullable=True),
        sa.Column("tolerance", sa.Numeric(15, 4), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_plan_steps_work_plan_id", "work_plan_steps", ["work_plan_id"]
    )

    # ── companies ─────────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column(
            "id", sa.BigInteger(), sa.ForeignKey("objects.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_type", sa.String(20), nullable=False),
        sa.Column("uid", sa.String(30), nullable=True),
        sa.Column("vat_id", sa.String(30), nullable=True),
        sa.Column("vat_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=False, server_default="CH"),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("payment_term_days", sa.BigInteger(), nullable=False, server_default="30"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_company_type", "companies", ["company_type"])

    # ── contacts ──────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column(
            "id", sa.BigInteger(), sa.ForeignKey("objects.id"), nullable=False
        ),
        sa.Column(
            "company_id",
            sa.BigInteger(),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column(
            "id", sa.BigInteger(), sa.ForeignKey("objects.id"), nullable=False
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "replaces_id",
            sa.BigInteger(),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
        sa.Column("applicable_from", sa.String(20), nullable=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── signatures ────────────────────────────────────────────────────────────
    op.create_table(
        "signatures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("context", sa.String(100), nullable=False),
        sa.Column("signer_id", sa.BigInteger(), nullable=False),
        sa.Column("signed_at_utc", sa.String(50), nullable=False),
        sa.Column("signature_png_path", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signatures_object_id", "signatures", ["object_id"])

    # ── attachments ───────────────────────────────────────────────────────────
    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_at_utc", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_object_id", "attachments", ["object_id"])

    # ── company_settings ──────────────────────────────────────────────────────
    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "company_name", sa.String(255), nullable=False, server_default="Inexxio AG"
        ),
        sa.Column("legal_form", sa.String(50), nullable=False, server_default="AG"),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("street_nr", sa.String(20), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column(
            "country", sa.String(100), nullable=False, server_default="Schweiz"
        ),
        sa.Column("uid_number", sa.String(30), nullable=True),
        sa.Column("vat_number", sa.String(30), nullable=True),
        sa.Column("trade_register_nr", sa.String(50), nullable=True),
        sa.Column("trade_register_canton", sa.String(50), nullable=True),
        sa.Column("share_capital", sa.String(100), nullable=True),
        sa.Column("iban_encrypted", sa.Text(), nullable=True),
        sa.Column("qr_iban_encrypted", sa.Text(), nullable=True),
        sa.Column("bank", sa.String(255), nullable=True),
        sa.Column("bic_swift", sa.String(20), nullable=True),
        sa.Column(
            "email",
            sa.String(255),
            nullable=False,
            server_default="info@inexxio.com",
        ),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column(
            "website",
            sa.String(255),
            nullable=False,
            server_default="https://inexxio.com",
        ),
        sa.Column(
            "vat_method", sa.String(50), nullable=False, server_default="effektiv"
        ),
        sa.Column(
            "vat_period", sa.String(20), nullable=False, server_default="quartal"
        ),
        sa.Column(
            "default_payment_days", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column("default_skonto_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("default_skonto_days", sa.Integer(), nullable=True),
        sa.Column("oss_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("oss_reg_number", sa.String(50), nullable=True),
        sa.Column("vies_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("stripe_publishable_key", sa.String(255), nullable=True),
        sa.Column("plausible_domain", sa.String(255), nullable=True),
        sa.Column("hcaptcha_site_key", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed default settings row
    op.execute(
        "INSERT INTO company_settings (id) VALUES (1) ON CONFLICT DO NOTHING"
    )

    # ── audit_log ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=True),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "changed_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("audit_log")
    op.drop_table("company_settings")
    op.drop_table("attachments")
    op.drop_table("signatures")
    op.drop_table("documents")
    op.drop_table("contacts")
    op.drop_table("companies")
    op.drop_table("work_plan_steps")
    op.drop_table("work_plans")
    op.drop_table("bom_lines")
    op.drop_table("boms")
    op.drop_table("items")
    op.drop_table("user_profiles")
    op.drop_table("objects")
    op.execute("DROP SEQUENCE IF EXISTS object_id_seq")
