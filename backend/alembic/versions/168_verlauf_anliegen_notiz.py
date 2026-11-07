"""Verlauf (Phase 2 «Die lernende Firma», Schritte 2.3/2.4): das Anliegen als Spalte, die
Beteiligten einer Nachricht als Datensatz statt Person.

* ``messages.topic`` – das **Anliegen** (Betreff in Normalform) mit Index ``(topic, at)``,
  damit «offen» eine Abfrage ist. **Gefüllt in Python, nicht in SQL**: die Normalform
  braucht ``str.casefold`` (aus «ß» wird «ss»), das PostgreSQL nicht kennt. Die Funktion
  steht hier **eingefroren** (``_topic``) – eine Abschrift von ``domain/communication.topic``
  am 06.11.2026; dass beide gleich rechnen, prüft ``tests/test_verlauf.py``. Ab jetzt setzt
  das Modell die Spalte mit dem Betreff (``Message._topic``).
* ``message_parties.object_id`` – der beteiligte **Datensatz** (An/Cc/Bcc eine Person,
  «Betrifft» jeder Datensatz). Gefüllt aus ``person_object_id``. **Zwei-Deploy-Regel**: die
  alte Spalte bleibt ungemappt stehen (``NOT NULL`` weg, damit neue Zeilen gehen) und fällt
  mit der nächsten Migration (``docs/backlog.md``). Bis dahin hält ein Trigger beide Spalten
  gleich – während des Ausrollens schreibt die alte Fassung noch ``person_object_id``.

Revision ID: 168
Revises: 167
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "168"
down_revision = "167"
branch_labels = None
depends_on = None

# ── eingefroren: domain/communication.topic (06.11.2026) ──────────────────────────────
_PREFIX = re.compile(r"^\s*((re|aw|antw|fw|fwd|wg|sv|vs|tr)\s*(\[\d+\])?\s*:\s*)+", re.I)


def _topic(subject):
    return re.sub(r"\s+", " ", _PREFIX.sub("", subject or "")).strip().casefold()


BRIDGE = """
CREATE OR REPLACE FUNCTION message_parties_bridge() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  NEW.object_id := coalesce(NEW.object_id, NEW.person_object_id);
  NEW.person_object_id := coalesce(NEW.person_object_id, NEW.object_id);
  RETURN NEW;
END;
$fn$;
DROP TRIGGER IF EXISTS trg_message_parties_bridge ON message_parties;
CREATE TRIGGER trg_message_parties_bridge BEFORE INSERT OR UPDATE ON message_parties
  FOR EACH ROW EXECUTE FUNCTION message_parties_bridge();
"""


def upgrade() -> None:
    op.execute("ALTER TABLE messages ADD COLUMN topic text NOT NULL DEFAULT ''")
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, subject FROM messages WHERE subject IS NOT NULL"))
    fill = [{"i": i, "t": _topic(s)} for i, s in rows if _topic(s)]
    if fill:
        bind.execute(sa.text("UPDATE messages SET topic = :t WHERE id = :i"), fill)
    op.execute("CREATE INDEX ix_messages_topic_at ON messages (topic, at)")

    op.execute("ALTER TABLE message_parties ADD COLUMN object_id bigint")
    op.execute("UPDATE message_parties SET object_id = person_object_id")
    op.execute("ALTER TABLE message_parties ALTER COLUMN object_id SET NOT NULL")
    op.execute("ALTER TABLE message_parties ALTER COLUMN person_object_id DROP NOT NULL")
    op.execute("CREATE INDEX ix_message_parties_object_id ON message_parties (object_id)")
    op.execute(BRIDGE)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_message_parties_bridge ON message_parties")
    op.execute("DROP FUNCTION IF EXISTS message_parties_bridge()")
    op.execute("UPDATE message_parties SET person_object_id = object_id "
               "WHERE person_object_id IS NULL")
    op.execute("ALTER TABLE message_parties ALTER COLUMN person_object_id SET NOT NULL")
    op.execute("DROP INDEX IF EXISTS ix_message_parties_object_id")
    op.execute("ALTER TABLE message_parties DROP COLUMN IF EXISTS object_id")
    op.execute("DROP INDEX IF EXISTS ix_messages_topic_at")
    op.execute("ALTER TABLE messages DROP COLUMN IF EXISTS topic")
