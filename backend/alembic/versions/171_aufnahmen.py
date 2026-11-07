"""Phase 4 · Sprache: die Stücke einer Aufnahme (``docs/konzept/phase4-bauplan.md``).

* ``recording_chunks`` – je Stück einer Aufnahme (Aufnahme = Log-Id von ``recording.start``,
  Abschnitt, Stück) seine Grösse und, nur ohne Bucket, die Bytes. **Eindeutig** je Aufnahme +
  Abschnitt + Stück: ein zweites Hochladen desselben Stücks ersetzt es. Technische Stücke,
  gelöscht nach der Abschrift (spätestens nach einem Tag) – nicht im Log (``domain/log.EXEMPT``).
  Kein Fremdschlüssel auf ``log`` (wie ``ai_memory``).
* ``ix_log_recording_segment`` – je Aufnahme und Abschnitt **eine** Abschrift
  (``recording.segment``): Anfrage und Takt schreiben nie dieselbe zweimal.
* ``ix_log_recording_end`` – je Aufnahme **ein** Ende (``recording.done`` oder
  ``recording.failed``) – nie zwei Erfassungen aus derselben Aufnahme.

Revision ID: 171
Revises: 170
"""

from alembic import op

revision = "171"
down_revision = "170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE TABLE recording_chunks (
    id bigserial PRIMARY KEY,
    recording bigint NOT NULL,
    segment integer NOT NULL,
    seq integer NOT NULL,
    byte_size integer NOT NULL,
    data bytea,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_recording_chunks_piece UNIQUE (recording, segment, seq)
)""")
    op.execute("CREATE INDEX ix_recording_chunks_recording ON recording_chunks (recording)")
    op.execute("CREATE UNIQUE INDEX ix_log_recording_segment ON log "
               "(((payload ->> 'recording')::bigint), ((payload ->> 'segment')::int)) "
               "WHERE event = 'recording.segment'")
    op.execute("CREATE UNIQUE INDEX ix_log_recording_end ON log "
               "(((payload ->> 'recording')::bigint)) "
               "WHERE event IN ('recording.done', 'recording.failed')")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_recording_end")
    op.execute("DROP INDEX IF EXISTS ix_log_recording_segment")
    op.execute("DROP TABLE IF EXISTS recording_chunks")
