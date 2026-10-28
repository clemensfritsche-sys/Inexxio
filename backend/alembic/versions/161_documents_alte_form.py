"""Die Tabelle ``documents`` des früheren Dokumentmoduls weicht der neuen (Oktober 2026).

Migration ``157`` legt ``documents`` mit ``CREATE TABLE IF NOT EXISTS`` an – wo die Tabelle
des **alten** Moduls (Migration ``050``, ohne ``object_id``) noch stand (dev, prod), blieb
deren Form, und kein Dokument liess sich anlegen oder finden
(``column documents.object_id does not exist``). Hier, nur wenn diese alte Form da ist:

1. die vier Tabellen der Ablage fallen (``documents`` samt den Verweisen darauf) – ein neues
   Dokument konnte dort nie entstehen, also hängt nichts daran; der Inhalt des alten Moduls
   ist laut Auftraggeber verzichtbar;
2. ``157`` legt sie in der richtigen Form neu an, ``voucher_documents.document_id`` zeigt
   wieder auf ``documents``.

Auf einer Datenbank mit der richtigen Form geschieht nichts.

Revision ID: 161
Revises: 160
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "161"
down_revision = "160"
branch_labels = None
depends_on = None


def _old_form() -> bool:
    insp = sa.inspect(op.get_bind())
    if "documents" not in insp.get_table_names():
        return False
    return "object_id" not in {c["name"] for c in insp.get_columns("documents")}


def _create_157() -> None:
    path = Path(__file__).with_name("157_dokumente.py")
    spec = importlib.util.spec_from_file_location("migration_157", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.upgrade()


def upgrade() -> None:
    if not _old_form():
        return
    op.execute("UPDATE voucher_documents SET document_id = NULL WHERE document_id IS NOT NULL")
    op.execute("DROP TABLE IF EXISTS document_links, document_signatures, document_refs")
    op.execute("DROP TABLE documents CASCADE")
    _create_157()
    op.execute("ALTER TABLE voucher_documents ADD CONSTRAINT voucher_documents_document_id_fkey "
               "FOREIGN KEY (document_id) REFERENCES documents (id)")


def downgrade() -> None:
    pass
