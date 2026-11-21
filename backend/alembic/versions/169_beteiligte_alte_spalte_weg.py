"""Zweiter Schritt nach 168 (Zwei-Deploy-Regel): ``message_parties.person_object_id`` fällt.

* Was die alte Fassung während des Ausrollens von 168 noch schrieb, wird nachgeholt: eine
  Nachricht mit Betreff, aber ohne **Anliegen** (``topic = ''``), bekommt es jetzt – mit
  derselben eingefrorenen Normalform wie in 168.
* Die Brücke (``trg_message_parties_bridge`` / ``message_parties_bridge()``) und die alte
  Spalte samt Index gehen.

Revision ID: 169
Revises: 168
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "169"
down_revision = "168"
branch_labels = None
depends_on = None

# ── eingefroren: domain/communication.topic (06.11.2026), wie in 168 ─────────────────────
_PREFIX = re.compile(r"^\s*((re|aw|antw|fw|fwd|wg|sv|vs|tr)\s*(\[\d+\])?\s*:\s*)+", re.I)


def _topic(subject):
    return re.sub(r"\s+", " ", _PREFIX.sub("", subject or "")).strip().casefold()


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, subject FROM messages WHERE topic = '' AND subject IS NOT NULL"))
    fill = [{"i": i, "t": _topic(s)} for i, s in rows if _topic(s)]
    if fill:
        bind.execute(sa.text("UPDATE messages SET topic = :t WHERE id = :i"), fill)
    op.execute("DROP TRIGGER IF EXISTS trg_message_parties_bridge ON message_parties")
    op.execute("DROP FUNCTION IF EXISTS message_parties_bridge()")
    op.execute("DROP INDEX IF EXISTS ix_message_parties_person_object_id")
    op.execute("ALTER TABLE message_parties DROP COLUMN IF EXISTS person_object_id")


def downgrade() -> None:
    op.execute("ALTER TABLE message_parties ADD COLUMN IF NOT EXISTS person_object_id bigint")
    op.execute("UPDATE message_parties SET person_object_id = object_id")
    op.execute("CREATE INDEX IF NOT EXISTS ix_message_parties_person_object_id "
               "ON message_parties (person_object_id)")
