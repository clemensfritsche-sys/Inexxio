"""User profile extensions: object_id, address, shipping, invoice, employment

Revision ID: 002
Revises: 001
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("object_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint("uq_user_profiles_object_id", "user_profiles", ["object_id"])
    op.create_index("ix_user_profiles_object_id", "user_profiles", ["object_id"])

    # Personal identity
    op.add_column("user_profiles", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("last_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("phone_mobile", sa.String(50), nullable=True))

    # Contact address
    op.add_column("user_profiles", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("address_line2", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("city", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("postal_code", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("state_canton", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("country", sa.String(100), nullable=False, server_default="CH"))

    # Shipping B2C
    op.add_column("user_profiles", sa.Column("ship_b2c_first_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_last_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_address_line1", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_address_line2", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_city", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_postal_code", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2c_country", sa.String(100), nullable=True))

    # Shipping B2B
    op.add_column("user_profiles", sa.Column("ship_b2b_company", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_contact", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_address_line1", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_address_line2", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_city", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_postal_code", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("ship_b2b_country", sa.String(100), nullable=True))

    # Invoice / billing
    op.add_column("user_profiles", sa.Column("invoice_company", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_first_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_last_name", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_address_line1", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_address_line2", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_city", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_postal_code", sa.String(20), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_country", sa.String(100), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_vat_id", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("invoice_email", sa.String(255), nullable=True))

    # Payment & billing
    op.add_column("user_profiles", sa.Column("payment_terms", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("user_profiles", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("user_profiles", sa.Column("preferred_currency", sa.String(10), nullable=False, server_default="CHF"))

    # Employee info
    op.add_column("user_profiles", sa.Column("employee_number", sa.String(50), nullable=True))
    op.add_column("user_profiles", sa.Column("employment_start_date", sa.Date(), nullable=True))

    # GDPR / marketing
    op.add_column("user_profiles", sa.Column("newsletter_opt_in", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    for col in [
        "newsletter_opt_in", "employment_start_date", "employee_number",
        "preferred_currency", "stripe_customer_id", "payment_terms",
        "invoice_email", "invoice_vat_id", "invoice_country", "invoice_postal_code",
        "invoice_city", "invoice_address_line2", "invoice_address_line1",
        "invoice_last_name", "invoice_first_name", "invoice_company",
        "ship_b2b_country", "ship_b2b_postal_code", "ship_b2b_city",
        "ship_b2b_address_line2", "ship_b2b_address_line1",
        "ship_b2b_contact", "ship_b2b_company",
        "ship_b2c_country", "ship_b2c_postal_code", "ship_b2c_city",
        "ship_b2c_address_line2", "ship_b2c_address_line1",
        "ship_b2c_last_name", "ship_b2c_first_name",
        "country", "state_canton", "postal_code", "city",
        "address_line2", "address_line1", "phone_mobile",
        "last_name", "first_name",
    ]:
        op.drop_column("user_profiles", col)

    op.drop_index("ix_user_profiles_object_id", "user_profiles")
    op.drop_constraint("uq_user_profiles_object_id", "user_profiles")
    op.drop_column("user_profiles", "object_id")
