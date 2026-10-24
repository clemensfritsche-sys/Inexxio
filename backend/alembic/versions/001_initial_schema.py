"""Initial schema — core tables only

Revision ID: 001
Revises:
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('object_id', sa.BigInteger(), nullable=True),
        sa.Column('firebase_uid', sa.String(128), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('photo_url', sa.Text(), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='customer'),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('phone_mobile', sa.String(50), nullable=True),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('state_canton', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=False, server_default='CH'),
        sa.Column('ship_b2c_first_name', sa.String(100), nullable=True),
        sa.Column('ship_b2c_last_name', sa.String(100), nullable=True),
        sa.Column('ship_b2c_address_line1', sa.String(255), nullable=True),
        sa.Column('ship_b2c_address_line2', sa.String(255), nullable=True),
        sa.Column('ship_b2c_city', sa.String(100), nullable=True),
        sa.Column('ship_b2c_postal_code', sa.String(20), nullable=True),
        sa.Column('ship_b2c_country', sa.String(100), nullable=True),
        sa.Column('ship_b2b_company', sa.String(255), nullable=True),
        sa.Column('ship_b2b_contact', sa.String(255), nullable=True),
        sa.Column('ship_b2b_address_line1', sa.String(255), nullable=True),
        sa.Column('ship_b2b_address_line2', sa.String(255), nullable=True),
        sa.Column('ship_b2b_city', sa.String(100), nullable=True),
        sa.Column('ship_b2b_postal_code', sa.String(20), nullable=True),
        sa.Column('ship_b2b_country', sa.String(100), nullable=True),
        sa.Column('invoice_company', sa.String(255), nullable=True),
        sa.Column('invoice_first_name', sa.String(100), nullable=True),
        sa.Column('invoice_last_name', sa.String(100), nullable=True),
        sa.Column('invoice_address_line1', sa.String(255), nullable=True),
        sa.Column('invoice_address_line2', sa.String(255), nullable=True),
        sa.Column('invoice_city', sa.String(100), nullable=True),
        sa.Column('invoice_postal_code', sa.String(20), nullable=True),
        sa.Column('invoice_country', sa.String(100), nullable=True),
        sa.Column('invoice_vat_id', sa.String(50), nullable=True),
        sa.Column('invoice_email', sa.String(255), nullable=True),
        sa.Column('invoice_same_as_shipping', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('salutation', sa.String(20), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('company_legal_form', sa.String(50), nullable=True),
        sa.Column('uid_number', sa.String(20), nullable=True),
        sa.Column('vat_number', sa.String(20), nullable=True),
        sa.Column('vat_registered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('trade_register_nr', sa.String(50), nullable=True),
        sa.Column('trade_register_canton', sa.String(50), nullable=True),
        sa.Column('company_website', sa.String(255), nullable=True),
        sa.Column('company_billing_email', sa.String(255), nullable=True),
        sa.Column('is_business', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('customer_group', sa.String(50), nullable=True),
        sa.Column('credit_limit', sa.Numeric(12, 2), nullable=True),
        sa.Column('accepts_marketing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('employment_start_date', sa.Date(), nullable=True),
        sa.Column('weekly_hours', sa.Numeric(5, 2), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='de'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Europe/Zurich'),
        sa.Column('notification_email', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notification_inapp', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('newsletter_opt_in', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('terms_version', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('firebase_uid'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('object_id'),
    )
    op.create_index('ix_user_profiles_firebase_uid', 'user_profiles', ['firebase_uid'])
    op.create_index('ix_user_profiles_email', 'user_profiles', ['email'])
    op.create_index('ix_user_profiles_object_id', 'user_profiles', ['object_id'])

    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('object_id', sa.BigInteger(), nullable=True),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('changed_at_utc', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at_utc', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])

    op.create_table(
        'company_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False, server_default='Inexxio AG'),
        sa.Column('legal_form', sa.String(50), nullable=False, server_default='AG'),
        sa.Column('street', sa.String(255), nullable=True),
        sa.Column('street_nr', sa.String(20), nullable=True),
        sa.Column('zip_code', sa.String(20), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=False, server_default='Schweiz'),
        sa.Column('uid_number', sa.String(30), nullable=True),
        sa.Column('vat_number', sa.String(30), nullable=True),
        sa.Column('trade_register_nr', sa.String(50), nullable=True),
        sa.Column('trade_register_canton', sa.String(50), nullable=True),
        sa.Column('share_capital', sa.String(100), nullable=True),
        sa.Column('iban_encrypted', sa.Text(), nullable=True),
        sa.Column('qr_iban_encrypted', sa.Text(), nullable=True),
        sa.Column('bank', sa.String(255), nullable=True),
        sa.Column('bic_swift', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=False, server_default='info@inexxio.com'),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('website', sa.String(255), nullable=False, server_default='https://inexxio.com'),
        sa.Column('vat_method', sa.String(50), nullable=False, server_default='effektiv'),
        sa.Column('vat_period', sa.String(20), nullable=False, server_default='quartal'),
        sa.Column('default_payment_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('default_skonto_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('default_skonto_days', sa.Integer(), nullable=True),
        sa.Column('oss_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('oss_reg_number', sa.String(50), nullable=True),
        sa.Column('vies_active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('logo_path', sa.String(500), nullable=True),
        sa.Column('stripe_publishable_key', sa.String(255), nullable=True),
        sa.Column('plausible_domain', sa.String(255), nullable=True),
        sa.Column('hcaptcha_site_key', sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('company_settings')
    op.drop_table('notifications')
    op.drop_table('audit_log')
    op.drop_table('user_profiles')
