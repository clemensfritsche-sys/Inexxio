"""Aufräumen 1, erster Deploy (``docs/history/2026-11-08-aufraeumen-1.md``).

* **Ein Pflichtfeld trägt genau ein Dokument** – ``uq_document_refs_field``; ältere doppelte
  aktive Referenzen werden vorher abgelöst (es bleibt die jüngste, wie sie gelesen wurde).
  Ausgenommen ``voucher.doc``: dort stehen alle Papiere eines Moduls.
* **Zwei-Deploy-Regel, Schritt 1**: Spalten, die kein Modell mehr kennt, bekommen eine Vorgabe
  bzw. dürfen leer sein, damit der neue Code ohne sie schreiben kann. Gedroppt werden sie im
  Folge-Deploy (Migration 176):
  ``is_active`` an 23 Tabellen, an denen nie gelöscht wird; ``created_by`` an
  ``attachments``, ``document_refs``, ``document_links``, ``holidays``; ``captures.captured_by``;
  ``articles.process_version``, ``process_steps.source_version``; ``orders.name`` (abgeleitet);
  ``instances.label`` (nie gesetzt); ``vouchers.original_id``/``export_photo_id`` (stehen im
  Pflichtfeld).
* Zwei eindeutige Indizes hingen an ``is_active`` dieser Tabellen – sie gelten jetzt ohne.
* Acht doppelte Indizes (ein ``ix_…`` neben dem eindeutigen ``…_key``) fallen.

Revision ID: 175
Revises: 174
"""

from alembic import op

revision = "175"
down_revision = "174"
branch_labels = None
depends_on = None

#: Tabellen, an denen ``is_active`` nie umgeschaltet wird (``models/base.SoftDeleteMixin``).
DEAD_ACTIVE = (
    "ai_memory", "article_process_steps", "articles", "attachments", "captures",
    "document_links", "document_signatures", "documents", "instance_units", "instances",
    "newsletter_consents", "order_lines", "order_units", "orders", "process_steps",
    "recording_chunks", "time_contracts", "time_entries", "user_profiles", "voucher_documents",
    "voucher_entries", "vouchers", "webauthn_challenges",
)

DUPLICATE_INDEXES = (
    "ix_articles_object_id", "ix_instances_object_id", "ix_orders_object_id",
    "ix_user_profiles_email", "ix_user_profiles_firebase_uid", "ix_user_profiles_object_id",
    "ix_webauthn_challenges_challenge", "ix_webauthn_credentials_credential_id",
)


def upgrade() -> None:
    op.execute("""
UPDATE document_refs r SET is_active = false
 WHERE r.is_active AND r.field IS NOT NULL
   AND EXISTS (SELECT 1 FROM document_refs n
                WHERE n.is_active AND n.field = r.field AND n.object_id = r.object_id
                  AND coalesce(n.part, '') = coalesce(r.part, '') AND n.id > r.id)
   AND r.field <> 'voucher.doc'""")
    op.execute("CREATE UNIQUE INDEX uq_document_refs_field ON document_refs "
               "(object_id, (coalesce(part, '')), field) "
               "WHERE is_active AND field IS NOT NULL AND field <> 'voucher.doc'")
    for table in DEAD_ACTIVE:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN is_active SET DEFAULT true")
    op.execute("ALTER TABLE orders ALTER COLUMN name DROP NOT NULL")
    op.execute("DROP INDEX IF EXISTS uq_vouchers_step")
    op.execute("CREATE UNIQUE INDEX uq_vouchers_step ON vouchers (step_id)")
    op.execute("DROP INDEX IF EXISTS uq_voucher_entries_reference")
    op.execute("CREATE UNIQUE INDEX uq_voucher_entries_reference ON voucher_entries (reference) "
               "WHERE reference IS NOT NULL")
    for name in DUPLICATE_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")


def downgrade() -> None:
    raise NotImplementedError("Aufräumen geht nur vorwärts.")
