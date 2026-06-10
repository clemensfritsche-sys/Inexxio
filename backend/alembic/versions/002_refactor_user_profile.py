"""Refactor user_profiles: remove legacy fields, add unified shipping and bank fields

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Migrate display_name into first_name / last_name where not yet set
    op.execute("""
        UPDATE user_profiles
        SET
            first_name = CASE
                WHEN first_name IS NULL AND display_name IS NOT NULL
                THEN split_part(display_name, ' ', 1)
                ELSE first_name
            END,
            last_name = CASE
                WHEN last_name IS NULL AND display_name IS NOT NULL
                     AND position(' ' IN display_name) > 0
                THEN substring(display_name FROM position(' ' IN display_name) + 1)
                ELSE last_name
            END
    """)

    # 2. Drop removed columns
    op.drop_column('user_profiles', 'display_name')
    op.drop_column('user_profiles', 'salutation')
    op.drop_column('user_profiles', 'phone_mobile')

    # Shipping B2C
    op.drop_column('user_profiles', 'ship_b2c_first_name')
    op.drop_column('user_profiles', 'ship_b2c_last_name')
    op.drop_column('user_profiles', 'ship_b2c_address_line1')
    op.drop_column('user_profiles', 'ship_b2c_address_line2')
    op.drop_column('user_profiles', 'ship_b2c_city')
    op.drop_column('user_profiles', 'ship_b2c_postal_code')
    op.drop_column('user_profiles', 'ship_b2c_country')

    # Shipping B2B
    op.drop_column('user_profiles', 'ship_b2b_company')
    op.drop_column('user_profiles', 'ship_b2b_contact')
    op.drop_column('user_profiles', 'ship_b2b_address_line1')
    op.drop_column('user_profiles', 'ship_b2b_address_line2')
    op.drop_column('user_profiles', 'ship_b2b_city')
    op.drop_column('user_profiles', 'ship_b2b_postal_code')
    op.drop_column('user_profiles', 'ship_b2b_country')

    # Invoice / billing
    op.drop_column('user_profiles', 'invoice_vat_id')

    # Business info
    op.drop_column('user_profiles', 'company_legal_form')

    # Preferences
    op.drop_column('user_profiles', 'timezone')

    # CRM
    op.drop_column('user_profiles', 'is_business')
    op.drop_column('user_profiles', 'customer_group')
    op.drop_column('user_profiles', 'credit_limit')
    op.drop_column('user_profiles', 'accepts_marketing')

    # Payment
    op.drop_column('user_profiles', 'stripe_customer_id')

    # 3. Rename state_canton -> state_region
    op.alter_column('user_profiles', 'state_canton', new_column_name='state_region')

    # 4. Add unified shipping columns
    op.add_column('user_profiles', sa.Column('ship_name', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_company', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_address_line1', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_address_line2', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_city', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_postal_code', sa.String(20), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_state_region', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_country', sa.String(100), nullable=True))

    # 5. Add bank detail columns
    op.add_column('user_profiles', sa.Column('bank_account_holder', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('bank_iban', sa.String(50), nullable=True))
    op.add_column('user_profiles', sa.Column('bank_bic', sa.String(20), nullable=True))
    op.add_column('user_profiles', sa.Column('bank_name', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove bank columns
    op.drop_column('user_profiles', 'bank_name')
    op.drop_column('user_profiles', 'bank_bic')
    op.drop_column('user_profiles', 'bank_iban')
    op.drop_column('user_profiles', 'bank_account_holder')

    # Remove unified shipping columns
    op.drop_column('user_profiles', 'ship_country')
    op.drop_column('user_profiles', 'ship_state_region')
    op.drop_column('user_profiles', 'ship_postal_code')
    op.drop_column('user_profiles', 'ship_city')
    op.drop_column('user_profiles', 'ship_address_line2')
    op.drop_column('user_profiles', 'ship_address_line1')
    op.drop_column('user_profiles', 'ship_company')
    op.drop_column('user_profiles', 'ship_name')

    # Rename state_region -> state_canton
    op.alter_column('user_profiles', 'state_region', new_column_name='state_canton')

    # Re-add removed columns
    op.add_column('user_profiles', sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('accepts_marketing', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('user_profiles', sa.Column('credit_limit', sa.Numeric(12, 2), nullable=True))
    op.add_column('user_profiles', sa.Column('customer_group', sa.String(50), nullable=True))
    op.add_column('user_profiles', sa.Column('is_business', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('user_profiles', sa.Column('timezone', sa.String(50), nullable=False, server_default='Europe/Zurich'))
    op.add_column('user_profiles', sa.Column('company_legal_form', sa.String(50), nullable=True))
    op.add_column('user_profiles', sa.Column('invoice_vat_id', sa.String(50), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_country', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_postal_code', sa.String(20), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_city', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_address_line2', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_address_line1', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_contact', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2b_company', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_country', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_postal_code', sa.String(20), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_city', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_address_line2', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_address_line1', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_last_name', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('ship_b2c_first_name', sa.String(100), nullable=True))
    op.add_column('user_profiles', sa.Column('phone_mobile', sa.String(50), nullable=True))
    op.add_column('user_profiles', sa.Column('salutation', sa.String(20), nullable=True))
    op.add_column('user_profiles', sa.Column('display_name', sa.String(255), nullable=True))
