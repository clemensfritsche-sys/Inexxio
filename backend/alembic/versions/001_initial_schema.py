"""Initial schema – Phase 1 core tables

Revision ID: 001
Revises:
Create Date: 2026-06-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Universal object sequence (9-digit IDs)
    op.execute("CREATE SEQUENCE IF NOT EXISTS object_id_seq START 100000001 INCREMENT 1")

    # Enums
    op.execute("CREATE TYPE objecttype AS ENUM ('item','bom','work_plan','production_order','purchase_order','sales_order','serialization','complaint','scrapping_record','maintenance_order','audit','capa','risk','document','invoice','credit_note','company','contact','user','contract','subscription')")
    op.execute("CREATE TYPE userrole AS ENUM ('admin','employee','supplier','customer')")
    op.execute("CREATE TYPE serialmode AS ENUM ('unit','batch')")
    op.execute("CREATE TYPE purchasetype AS ENUM ('one_time','subscription','both')")
    op.execute("CREATE TYPE companytype AS ENUM ('customer','supplier','both')")
    op.execute("CREATE TYPE steptype AS ENUM ('operation','qc_check')")

    # objects table
    op.create_table(
        "objects",
        sa.Column("id", sa.BigInteger(), server_default=sa.text("nextval('object_id_seq')"), nullable=False),
        sa.Column("object_type", postgresql.ENUM("item","bom","work_plan","production_order","purchase_order","sales_order","serialization","complaint","scrapping_record","maintenance_order","audit","capa","risk","document","invoice","credit_note","company","contact","user","contract","subscription", name="objecttype", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_objects_object_type", "objects", ["object_type"])
    op.create_index("ix_objects_is_active", "objects", ["is_active"])

    # users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("firebase_uid", sa.String(128), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("role", postgresql.ENUM("admin","employee","supplier","customer", name="userrole", create_type=False), server_default="customer", nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("function", sa.String(100), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("language", sa.String(10), server_default="de", nullable=False),
        sa.Column("timezone", sa.String(50), server_default="Europe/Zurich", nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("weekly_hours", sa.Numeric(4, 1), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_version", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_shadow", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("firebase_uid"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_firebase_uid", "users", ["firebase_uid"])
    op.create_index("ix_users_email", "users", ["email"])

    # companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_type", postgresql.ENUM("customer","supplier","both", name="companytype", create_type=False), nullable=False),
        sa.Column("uid", sa.String(50), nullable=True),
        sa.Column("vat_id", sa.String(50), nullable=True),
        sa.Column("vat_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", postgresql.JSONB(), nullable=True),
        sa.Column("country_code", sa.String(2), server_default="CH", nullable=False),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("payment_term_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])

    # contacts table
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # items table
    op.create_table(
        "items",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("size", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(20), server_default="Stk", nullable=False),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_equipment", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("serial_mode", postgresql.ENUM("unit","batch", name="serialmode", create_type=False), server_default="unit", nullable=False),
        sa.Column("replaced_by_id", sa.BigInteger(), nullable=True),
        sa.Column("replaces_id", sa.BigInteger(), nullable=True),
        sa.Column("is_sales_product", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("shop_description", sa.Text(), nullable=True),
        sa.Column("purchase_type", postgresql.ENUM("one_time","subscription","both", name="purchasetype", create_type=False), server_default="one_time", nullable=True),
        sa.Column("list_price_chf", sa.Numeric(12, 4), nullable=True),
        sa.Column("hs_code", sa.String(20), nullable=True),
        sa.Column("min_stock", sa.Numeric(12, 3), nullable=True),
        sa.Column("reorder_point", sa.Numeric(12, 3), nullable=True),
        sa.Column("max_stock", sa.Numeric(12, 3), nullable=True),
        sa.Column("preferred_supplier_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("is_approved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["replaces_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_items_name", "items", ["name"])
    op.create_index("ix_items_category", "items", ["category"])

    # boms table
    op.create_table(
        "boms",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("parent_item_id", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["parent_item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # bom_lines table
    op.create_table(
        "bom_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bom_id", sa.BigInteger(), nullable=False),
        sa.Column("component_item_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(20), server_default="Stk", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["bom_id"], ["boms.id"]),
        sa.ForeignKeyConstraint(["component_item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # work_plans table
    op.create_table(
        "work_plans",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("item_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["id"], ["objects.id"]),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # work_plan_steps table
    op.create_table(
        "work_plan_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("step_nr", sa.Integer(), nullable=False),
        sa.Column("step_type", postgresql.ENUM("operation","qc_check", name="steptype", create_type=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("resource", sa.String(100), nullable=True),
        sa.Column("setup_min", sa.Numeric(8, 2), nullable=True),
        sa.Column("exec_min_per_unit", sa.Numeric(8, 2), nullable=True),
        sa.Column("nominal_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("tolerance", sa.Numeric(12, 4), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["work_plan_id"], ["work_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # audit_log table
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("changed_at_utc", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_object_id", "audit_log", ["object_id"])
    op.create_index("ix_audit_log_changed_at_utc", "audit_log", ["changed_at_utc"])

    # signatures table
    op.create_table(
        "signatures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("context", sa.String(100), nullable=False),
        sa.Column("signer_id", sa.BigInteger(), nullable=False),
        sa.Column("signed_at_utc", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("signature_png_path", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # attachments table
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=True),
        sa.Column("uploaded_at_utc", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("link", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # company_settings table (single-row config)
    op.create_table(
        "company_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(255), server_default="Inexxio AG", nullable=True),
        sa.Column("legal_form", sa.String(50), server_default="AG", nullable=True),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), server_default="Schweiz", nullable=True),
        sa.Column("uid_number", sa.String(50), nullable=True),
        sa.Column("vat_number", sa.String(50), nullable=True),
        sa.Column("commercial_register_nr", sa.String(50), nullable=True),
        sa.Column("commercial_register_canton", sa.String(50), nullable=True),
        sa.Column("share_capital", sa.Numeric(14, 2), nullable=True),
        sa.Column("iban", sa.String(34), nullable=True),
        sa.Column("qr_iban", sa.String(34), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bic_swift", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), server_default="info@inexxio.com", nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("website", sa.String(255), server_default="https://inexxio.com", nullable=True),
        sa.Column("logo_path", sa.Text(), nullable=True),
        sa.Column("vat_method", sa.String(50), server_default="effektiv", nullable=True),
        sa.Column("vat_period", sa.String(20), server_default="quartal", nullable=True),
        sa.Column("default_payment_term_days", sa.Integer(), server_default="30", nullable=True),
        sa.Column("default_skonto_pct", sa.Numeric(5, 2), server_default="2.0", nullable=True),
        sa.Column("default_skonto_days", sa.Integer(), server_default="10", nullable=True),
        sa.Column("oss_active", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("oss_registration_nr", sa.String(50), nullable=True),
        sa.Column("vies_active", sa.Boolean(), server_default="false", nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Insert default single row
    op.execute("INSERT INTO company_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("company_settings")
    op.drop_table("notifications")
    op.drop_table("attachments")
    op.drop_table("signatures")
    op.drop_table("audit_log")
    op.drop_table("work_plan_steps")
    op.drop_table("work_plans")
    op.drop_table("bom_lines")
    op.drop_table("boms")
    op.drop_table("items")
    op.drop_table("contacts")
    op.drop_table("companies")
    op.drop_table("users")
    op.drop_table("objects")
    op.execute("DROP SEQUENCE IF EXISTS object_id_seq")
    op.execute("DROP TYPE IF EXISTS steptype")
    op.execute("DROP TYPE IF EXISTS companytype")
    op.execute("DROP TYPE IF EXISTS purchasetype")
    op.execute("DROP TYPE IF EXISTS serialmode")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS objecttype")
