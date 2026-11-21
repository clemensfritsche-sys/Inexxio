"""Wiederkehr: je Auftrag höchstens ein Nachfolger (Projektakte ``docs/konzept/wiederkehr.md``).

Die Schlaufe ist keine Tabelle, sondern drei Ereignisse im Log (``services/loop``): ``loop.set``
(die eingefrorene Schlaufe am Auftrag), ``loop.next`` (der Nachfolger, ``from`` = Vorgänger),
``loop.ended``. Zwei Indizes, gebaut wie ``ix_log_decided`` (Migration 170):

* ``ix_log_loop_next``: **eindeutig** je Vorgänger – ein zweiter Nachfolger (zwei Läufe des
  Takts, ein Fehler im Code) scheitert an der Datenbank, nicht an einer Prüfung.
* ``ix_log_loop``: die Ereignisse der Schlaufe je Auftrag – «läuft, beendet?» liest genau das.

Revision ID: 173
Revises: 172
"""

from alembic import op

revision = "173"
down_revision = "172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX ix_log_loop_next ON log (((payload ->> 'from')::bigint)) "
               "WHERE event = 'loop.next'")
    op.execute("CREATE INDEX ix_log_loop ON log (object_id, event) "
               "WHERE event IN ('loop.set', 'loop.next', 'loop.ended', 'loop.agreed')")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_loop")
    op.execute("DROP INDEX IF EXISTS ix_log_loop_next")
