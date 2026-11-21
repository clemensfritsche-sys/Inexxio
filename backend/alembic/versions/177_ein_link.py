"""Ein Link für jedes Papier (Aufräumen, Stufe 4b): die Papiere eines Belegs gehen über
``document_links`` hinaus wie jedes gesendete Dokument; was ein Papier ist (Art, Nummer,
Mahnstufe, AGB), steht am Dokument (``facts``). ``voucher_documents`` ist damit entmappt und fällt
im Folge-Deploy (Zwei-Deploy-Regel).

Revision ID: 177
Revises: 176
"""

from alembic import op

revision = "177"
down_revision = "176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
INSERT INTO document_links (token, document_id, person_object_id, message_id, created_at, updated_at)
SELECT v.token, v.document_id, v.party_id, v.message_id, v.created_at, v.updated_at
  FROM voucher_documents v
 WHERE v.document_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM document_links l WHERE l.token = v.token)""")
    op.execute("""
UPDATE documents d
   SET facts = coalesce(d.facts, '{}'::jsonb)
             || jsonb_build_object('kind', v.kind, 'number', v.number, 'level', v.level,
                                   'agb', v.agb)
  FROM voucher_documents v
 WHERE v.document_id = d.id""")


def downgrade() -> None:
    raise RuntimeError("Ein Link für jedes Papier – kein Weg zurück.")
