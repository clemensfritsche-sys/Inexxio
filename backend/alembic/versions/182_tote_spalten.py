"""Aufräumen A1, Deploy 2: die Spalten, die niemand liest, fallen (Änderungsakte §6).

Entmappt mit 181 (Zwei-Deploy-Regel). Der Fremdschlüssel an
``process_steps.source_article_id`` fällt mit seiner Spalte.

Revision ID: 182
Revises: 181
"""

from alembic import op

revision = "182"
down_revision = "181"
branch_labels = None
depends_on = None

_GONE = {
    "captures": ("note", "varchar(500)"),
    "process_steps": ("source_article_id", "bigint"),
    "webauthn_credentials.transports": ("transports", "jsonb"),
    "webauthn_credentials.device_type": ("device_type", "varchar(20)"),
    "attachments.width": ("width", "integer"),
    "attachments.height": ("height", "integer"),
}


def _table(key: str) -> str:
    return key.split(".")[0]


def upgrade() -> None:
    for key, (column, _) in _GONE.items():
        op.execute(f"ALTER TABLE {_table(key)} DROP COLUMN IF EXISTS {column}")


def downgrade() -> None:
    for key, (column, kind) in _GONE.items():
        op.execute(f"ALTER TABLE {_table(key)} ADD COLUMN IF NOT EXISTS {column} {kind}")
