"""Datei-Ablage (Oktober 2026): die Bytes einer Datei liegen in Cloud Storage.

``attachments.data`` darf leer sein – dann hält der Bucket der Umgebung die Datei (Objektname
= Token). Ohne Bucket bleiben die Bytes in der Zeile (``services/attachments.keep``).

Revision ID: 159
Revises: 158
"""

from alembic import op

revision = "159"
down_revision = "158"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE attachments ALTER COLUMN data DROP NOT NULL")


def downgrade() -> None:
    pass
