"""Phase 5 «Der Assistent»: Gespräch und Handgriff statt Erfassung und Vorschlag
(``docs/konzept/phase5-bauplan.md``). Nicht rückwärtskompatibel.

* ``ix_log_decided`` fällt (es gibt keine Vorschläge mehr).
* ``ix_log_handgriff_done``: **eindeutig** je Handgriff – ein zweites Ausführen (zwei Klicks,
  zwei Fenster) scheitert an der Datenbank, nicht an einer Prüfung.
* ``ix_log_handgriff_dropped``: «weggelegt?» liest genau das.
* ``ix_log_talk``: die Nachrichten eines Gesprächs.
* ``ai_memory`` neu: je Eintrag Art und Nummer (ein entschiedener Handgriff, eine Notiz, ein
  Dokument) – «im Wissen suchen». Eine Ableitung: der Takt baut sie neu auf, die alten Fälle
  (Vorschläge) gibt es nicht mehr.

Revision ID: 174
Revises: 173
"""

from alembic import op

revision = "174"
down_revision = "173"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_decided")
    op.execute("CREATE UNIQUE INDEX ix_log_handgriff_done ON log "
               "(((payload ->> 'handgriff')::bigint)) WHERE event = 'handgriff.done'")
    op.execute("CREATE INDEX ix_log_handgriff_dropped ON log "
               "(((payload ->> 'handgriff')::bigint)) WHERE event = 'handgriff.dropped'")
    op.execute("CREATE INDEX ix_log_talk ON log (((payload ->> 'talk')::bigint)) "
               "WHERE event IN ('talk', 'handgriff')")
    op.execute("DROP TABLE IF EXISTS ai_memory")
    op.execute("""
CREATE TABLE ai_memory (
    kind varchar(12) NOT NULL,
    ref_id bigint NOT NULL,
    at timestamptz NOT NULL,
    embedding vector(768) NOT NULL,
    text text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, ref_id)
)""")
    op.execute("CREATE INDEX ix_ai_memory_embedding ON ai_memory "
               "USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    raise RuntimeError("Phase 5 ist nicht rückwärtskompatibel – kein Weg zurück.")
