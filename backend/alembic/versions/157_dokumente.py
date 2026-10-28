"""Dokumente (Oktober 2026): jede freigegebene Datei ist ein Datensatz.

* ``documents`` – Nummer, Art, Name, Quelle, Datei im Korb (``attachments``), Prüfsumme,
  Gelesenes; gelöscht bleibt der Datensatz (``deleted_*``).
* ``document_refs`` – die EINE Verbindung zu einem Datensatz (ggf. Teil, ggf. Pflichtfeld).
* ``document_signatures`` – verlangte Unterschriften, nur anfügen.
* ``document_links`` – Links nach aussen, je Empfänger einer, ohne Ablauf.
* ``audit_log.on_behalf`` – in wessen Namen (Mensch · KI · System).

Revision ID: 157
Revises: 156
"""

from alembic import op

revision = "157"
down_revision = "156"
branch_labels = None
depends_on = None

_STAMPS = "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, " \
          "is_active BOOLEAN NOT NULL"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS documents (
            id BIGSERIAL PRIMARY KEY,
            object_id BIGINT NOT NULL,
            art VARCHAR(80) NOT NULL,
            name VARCHAR(200) NOT NULL,
            source VARCHAR(12) NOT NULL,
            file_id BIGINT,
            mime VARCHAR(100) NOT NULL,
            filename VARCHAR(255),
            byte_size INTEGER NOT NULL,
            sha256 VARCHAR(64),
            text TEXT,
            keywords TEXT,
            facts JSONB,
            created_by BIGINT,
            deleted_at TIMESTAMPTZ,
            deleted_by BIGINT,
            delete_reason VARCHAR(300),
            {_STAMPS}
        )""")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_object_id ON documents (object_id)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_sha256 "
               "ON documents (sha256) WHERE deleted_at IS NULL AND sha256 IS NOT NULL")
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS document_refs (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
            object_id BIGINT NOT NULL,
            part VARCHAR(60),
            field VARCHAR(40),
            created_by BIGINT,
            {_STAMPS}
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_refs_document_id ON document_refs (document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_refs_object_id ON document_refs (object_id)")
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS document_signatures (
            id BIGSERIAL PRIMARY KEY,
            document_id BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
            person_object_id BIGINT NOT NULL,
            name VARCHAR(200) NOT NULL,
            signed_at TIMESTAMPTZ,
            declined_at TIMESTAMPTZ,
            reason VARCHAR(300),
            image BYTEA,
            sha256 VARCHAR(64),
            {_STAMPS}
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_signatures_document_id "
               "ON document_signatures (document_id)")
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS document_links (
            id BIGSERIAL PRIMARY KEY,
            token VARCHAR(64) NOT NULL UNIQUE,
            document_id BIGINT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
            person_object_id BIGINT,
            message_id BIGINT,
            created_by BIGINT,
            {_STAMPS}
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_document_links_document_id "
               "ON document_links (document_id)")
    op.execute("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS on_behalf VARCHAR(12)")


def downgrade() -> None:
    pass
