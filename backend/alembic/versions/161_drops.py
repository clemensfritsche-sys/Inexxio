"""Folge-Deploy (Oktober 2026): die zwei Spalten ohne Mapping fallen (Zwei-Deploy-Regel).

* ``company_settings.google_maps_api_key`` – der Schlüssel kommt aus der Deploy-Konfiguration.
* ``user_profiles.newsletter_opt_in`` – die Einwilligung ist ein Nachweis (Migration 153).

Revision ID: 161
Revises: 160
"""

from alembic import op

revision = "161"
down_revision = "160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE company_settings DROP COLUMN IF EXISTS google_maps_api_key")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS newsletter_opt_in")


def downgrade() -> None:
    pass
