"""Refactor user_profiles: remove legacy fields, add unified shipping and bank fields

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, 'user_profiles')

    # 1. Migrate display_name → first_name / last_name
    if 'display_name' in cols:
        bind.execute(text("""
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
            WHERE display_name IS NOT NULL
        """))

    # 2. Drop removed columns
    for col in [
        'display_name', 'salutation', 'phone_mobile',
        'ship_b2c_first_name', 'ship_b2c_last_name', 'ship_b2c_address_line1',
        'ship_b2c_address_line2', 'ship_b2c_city', 'ship_b2c_postal_code', 'ship_b2c_country',
        'ship_b2b_company', 'ship_b2b_contact', 'ship_b2b_address_line1',
        'ship_b2b_address_line2', 'ship_b2b_city', 'ship_b2b_postal_code', 'ship_b2b_country',
        'invoice_vat_id', 'company_legal_form', 'timezone',
        'is_business', 'customer_group', 'credit_limit', 'accepts_marketing', 'stripe_customer_id',
    ]:
        if col in cols:
            op.drop_column('user_profiles', col)

    # 3. Rename state_canton → state_region
    cols = _columns(bind, 'user_profiles')  # re-read after drops
    if 'state_canton' in cols and 'state_region' not in cols:
        op.alter_column('user_profiles', 'state_canton', new_column_name='state_region')
    elif 'state_canton' in cols and 'state_region' in cols:
        op.drop_column('user_profiles', 'state_canton')
    elif 'state_region' not in cols:
        op.add_column('user_profiles', sa.Column('state_region', sa.String(100), nullable=True))

    # 4. Add unified shipping columns
    cols = _columns(bind, 'user_profiles')
    ship_cols = {
        'ship_name': sa.String(255), 'ship_company': sa.String(255),
        'ship_address_line1': sa.String(255), 'ship_address_line2': sa.String(255),
        'ship_city': sa.String(100), 'ship_postal_code': sa.String(20),
        'ship_state_region': sa.String(100), 'ship_country': sa.String(100),
    }
    for col_name, col_type in ship_cols.items():
        if col_name not in cols:
            op.add_column('user_profiles', sa.Column(col_name, col_type, nullable=True))

    # 5. Add bank columns
    bank_cols = {
        'bank_account_holder': sa.String(255), 'bank_iban': sa.String(50),
        'bank_bic': sa.String(20), 'bank_name': sa.String(255),
    }
    for col_name, col_type in bank_cols.items():
        if col_name not in cols:
            op.add_column('user_profiles', sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind, 'user_profiles')

    for col in [
        'bank_name', 'bank_bic', 'bank_iban', 'bank_account_holder',
        'ship_country', 'ship_state_region', 'ship_postal_code', 'ship_city',
        'ship_address_line2', 'ship_address_line1', 'ship_company', 'ship_name',
    ]:
        if col in cols:
            op.drop_column('user_profiles', col)

    cols = _columns(bind, 'user_profiles')
    if 'state_region' in cols and 'state_canton' not in cols:
        op.alter_column('user_profiles', 'state_region', new_column_name='state_canton')

    cols = _columns(bind, 'user_profiles')
    restore = {
        'stripe_customer_id': sa.String(255), 'credit_limit': sa.Numeric(12, 2),
        'customer_group': sa.String(50), 'company_legal_form': sa.String(50),
        'invoice_vat_id': sa.String(50),
        'ship_b2b_country': sa.String(100), 'ship_b2b_postal_code': sa.String(20),
        'ship_b2b_city': sa.String(100), 'ship_b2b_address_line2': sa.String(255),
        'ship_b2b_address_line1': sa.String(255), 'ship_b2b_contact': sa.String(255),
        'ship_b2b_company': sa.String(255),
        'ship_b2c_country': sa.String(100), 'ship_b2c_postal_code': sa.String(20),
        'ship_b2c_city': sa.String(100), 'ship_b2c_address_line2': sa.String(255),
        'ship_b2c_address_line1': sa.String(255), 'ship_b2c_last_name': sa.String(100),
        'ship_b2c_first_name': sa.String(100), 'phone_mobile': sa.String(50),
        'salutation': sa.String(20), 'display_name': sa.String(255),
    }
    for col_name, col_type in restore.items():
        if col_name not in cols:
            op.add_column('user_profiles', sa.Column(col_name, col_type, nullable=True))
