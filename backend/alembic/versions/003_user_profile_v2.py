"""User profile v2: add company/shop fields, remove payment_terms/preferred_currency/employee_number

Revision ID: 003
Revises: 002
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Personal extras
    op.add_column("user_profiles", sa.Column("salutation", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))

    # Business / company info
    op.add_column("user_profiles", sa.Column("company_name", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("company_legal_form", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("uid_number", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("vat_number", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("vat_registered", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("user_profiles", sa.Column("trade_register_nr", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("trade_register_canton", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("company_website", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("company_billing_email", sa.String(255), nullable=True))

    # Online shop / CRM
    op.add_column("user_profiles", sa.Column("customer_group", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("credit_limit", sa.Numeric(12, 2), nullable=True))
    op.add_column("user_profiles", sa.Column("accepts_marketing", sa.Boolean(), nullable=False, server_default="false"))

    # Drop obsolete columns
    op.drop_column("user_profiles", "payment_terms")
    op.drop_column("user_profiles", "preferred_currency")
    op.drop_column("user_profiles", "employee_number")


def downgrade() -> None:
    op.add_column("user_profiles", sa.Column("payment_terms", sa.Integer(), server_default="30", nullable=False))
    op.add_column("user_profiles", sa.Column("preferred_currency", sa.String(10), server_default="CHF", nullable=False))
    op.add_column("user_profiles", sa.Column("employee_number", sa.String(50), nullable=True))

    op.drop_column("user_profiles", "accepts_marketing")
    op.drop_column("user_profiles", "credit_limit")
    op.drop_column("user_profiles", "customer_group")
    op.drop_column("user_profiles", "company_billing_email")
    op.drop_column("user_profiles", "company_website")
    op.drop_column("user_profiles", "trade_register_canton")
    op.drop_column("user_profiles", "trade_register_nr")
    op.drop_column("user_profiles", "vat_registered")
    op.drop_column("user_profiles", "vat_number")
    op.drop_column("user_profiles", "uid_number")
    op.drop_column("user_profiles", "company_legal_form")
    op.drop_column("user_profiles", "company_name")
    op.drop_column("user_profiles", "date_of_birth")
    op.drop_column("user_profiles", "salutation")
