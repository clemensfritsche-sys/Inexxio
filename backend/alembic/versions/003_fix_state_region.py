"""Fix state_region column: handle all possible DB states from migration 002

Revision ID: 003
Revises: 002
Create Date: 2026-06-10
"""
from alembic import op

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Handle all four possible states after migration 002:
    # 1. state_canton exists, state_region does NOT → rename
    # 2. state_canton exists, state_region also exists → drop state_canton
    # 3. Neither exists → add state_region
    # 4. state_region exists, state_canton does NOT → already correct, no-op
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'user_profiles'
                  AND column_name = 'state_canton'
            ) THEN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'user_profiles'
                      AND column_name = 'state_region'
                ) THEN
                    -- Case 1: rename
                    ALTER TABLE user_profiles RENAME COLUMN state_canton TO state_region;
                ELSE
                    -- Case 2: both exist, drop the old one
                    ALTER TABLE user_profiles DROP COLUMN state_canton;
                END IF;
            ELSIF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'user_profiles'
                  AND column_name = 'state_region'
            ) THEN
                -- Case 3: neither exists, add fresh
                ALTER TABLE user_profiles ADD COLUMN state_region VARCHAR(100);
            END IF;
            -- Case 4: state_region already exists, state_canton gone → no-op
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'user_profiles'
                  AND column_name = 'state_region'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'user_profiles'
                  AND column_name = 'state_canton'
            ) THEN
                ALTER TABLE user_profiles RENAME COLUMN state_region TO state_canton;
            END IF;
        END $$;
    """)
