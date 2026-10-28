"""Eine Ablage (Oktober 2026): das Papier eines Belegs ist ein Dokument.

* ``voucher_documents.document_id`` – das Dokument (Feld ``voucher.doc``); die Zeile hält nur
  noch, wie es hinausging (Link, Partei, Mail).
* ``voucher_documents.html`` darf leer sein – das Papier steht im Dokument. Die Spalte fällt
  im Folge-Deploy weg (Zwei-Deploy-Regel).

Die Übernahme der bestehenden Papiere, Lieferantenrechnungen, Ausfuhrnachweise und
Rechtstexte braucht die Fachschicht (Nummernkreis, Korb) und läuft beim Start
(``services/adopt``), selbstbegrenzend.

Revision ID: 158
Revises: 157
"""

from alembic import op

revision = "158"
down_revision = "157"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE voucher_documents ADD COLUMN IF NOT EXISTS document_id BIGINT "
               "REFERENCES documents(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_voucher_documents_document_id "
               "ON voucher_documents (document_id)")
    op.execute("ALTER TABLE voucher_documents ALTER COLUMN html DROP NOT NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_voucher_documents_document_id")
    op.execute("ALTER TABLE voucher_documents DROP COLUMN IF EXISTS document_id")
