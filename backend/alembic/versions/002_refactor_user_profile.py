"""Refactor user_profiles: remove legacy fields, add unified shipping and bank fields

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
from alembic import op

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Migrate display_name → first_name / last_name where not yet set
    #    Guarded: only runs if display_name column still exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_profiles' AND column_name = 'display_name'
            ) THEN
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
                WHERE display_name IS NOT NULL;
            END IF;
        END $$;
    """)

    # 2. Drop removed columns (IF EXISTS — safe to re-run)
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS display_name")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS salutation")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS phone_mobile")

    # Shipping B2C
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_first_name")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_last_name")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_address_line1")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_address_line2")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_city")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_postal_code")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2c_country")

    # Shipping B2B
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_company")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_contact")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_address_line1")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_address_line2")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_city")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_postal_code")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_b2b_country")

    # Invoice / business / preferences / CRM / payment
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS invoice_vat_id")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS company_legal_form")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS timezone")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS is_business")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS customer_group")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS credit_limit")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS accepts_marketing")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS stripe_customer_id")

    # 3. Rename state_canton → state_region (only if state_canton still exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_profiles' AND column_name = 'state_canton'
            ) THEN
                ALTER TABLE user_profiles RENAME COLUMN state_canton TO state_region;
            END IF;
        END $$;
    """)

    # 4. Add unified shipping columns (IF NOT EXISTS — safe to re-run)
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_name VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_company VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_address_line1 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_address_line2 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_city VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_postal_code VARCHAR(20)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_state_region VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_country VARCHAR(100)")

    # 5. Add bank detail columns (IF NOT EXISTS — safe to re-run)
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS bank_account_holder VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS bank_iban VARCHAR(50)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS bank_bic VARCHAR(20)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255)")


def downgrade() -> None:
    # Remove bank columns
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS bank_name")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS bank_bic")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS bank_iban")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS bank_account_holder")

    # Remove unified shipping columns
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_country")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_state_region")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_postal_code")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_city")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_address_line2")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_address_line1")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_company")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS ship_name")

    # Rename state_region → state_canton
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_profiles' AND column_name = 'state_region'
            ) THEN
                ALTER TABLE user_profiles RENAME COLUMN state_region TO state_canton;
            END IF;
        END $$;
    """)

    # Re-add removed columns
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS accepts_marketing BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS credit_limit NUMERIC(12,2)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS customer_group VARCHAR(50)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_business BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) NOT NULL DEFAULT 'Europe/Zurich'")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS company_legal_form VARCHAR(50)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS invoice_vat_id VARCHAR(50)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_country VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_postal_code VARCHAR(20)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_city VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_address_line2 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_address_line1 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_contact VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2b_company VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_country VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_postal_code VARCHAR(20)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_city VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_address_line2 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_address_line1 VARCHAR(255)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_last_name VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS ship_b2c_first_name VARCHAR(100)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS phone_mobile VARCHAR(50)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS salutation VARCHAR(20)")
    op.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS display_name VARCHAR(255)")
