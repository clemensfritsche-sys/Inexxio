"""Das Gedächtnis der KI (Projektakte «Die lernende Firma» §4.3, Schritt 3.6).

* ``vector`` (pgvector) – Bedeutungs-Zahlen in der eigenen Datenbank; Cloud SQL für
  PostgreSQL bringt die Erweiterung mit (``CREATE EXTENSION`` darf der Eigentümer der DB).
* ``ai_memory`` – je Vorschlag (``log.id``) seine 768 Zahlen und der Text dazu. Eine Ableitung
  aus dem Log: kein Fremdschlüssel auf ``log`` (das Log ist unveränderlich und wird nie
  gelöscht; die Zeile hier darf neu entstehen).
* Der Index (HNSW, Kosinus) trägt «die ähnlichsten Fälle» auch bei vielen tausend Fällen.
* ``ix_log_decided``: der Entscheid zu einem Vorschlag (``proposal.decided`` → ``proposal``) –
  «ist er offen?» und «wie wurde entschieden?» lesen genau das.

Revision ID: 170
Revises: 169
"""

from alembic import op

revision = "170"
down_revision = "169"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
CREATE TABLE ai_memory (
    log_id bigint PRIMARY KEY,
    embedding vector(768) NOT NULL,
    text text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
)""")
    op.execute("CREATE INDEX ix_ai_memory_embedding ON ai_memory "
               "USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_log_decided ON log (((payload ->> 'proposal')::bigint)) "
               "WHERE event = 'proposal.decided'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_log_decided")
    op.execute("DROP TABLE IF EXISTS ai_memory")
