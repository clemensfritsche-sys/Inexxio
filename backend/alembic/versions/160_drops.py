"""Folge-Deploy (Oktober 2026): die Spalten ohne Mapping fallen (Zwei-Deploy-Regel).

* ``voucher_documents.html`` – das Papier steht im Dokument (Migration 158).
* ``user_profiles.employment_start_date`` · ``weekly_hours`` – im Vertrag (Migration 154).

Revision ID: 160
Revises: 159
"""

from alembic import op

revision = "160"
down_revision = "159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE voucher_documents DROP COLUMN IF EXISTS html")
    for col in ("employment_start_date", "weekly_hours"):
        op.execute(f"ALTER TABLE user_profiles DROP COLUMN IF EXISTS {col}")


def downgrade() -> None:
    pass
