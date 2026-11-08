"""Aufräumen 1, zweiter Deploy: die Spalten fallen, die Migration 175 entmappt hat
(Zwei-Deploy-Regel, ``docs/backlog.md``), und die IBAN-Spalte heisst, was sie ist.

* ``is_active`` an 23 Tabellen, an denen nie gelöscht wird.
* ``created_by`` an ``attachments``, ``document_refs``, ``document_links``, ``holidays``;
  ``captures.captured_by`` (das Log hält fest, wer handelte).
* ``articles.process_version``, ``process_steps.source_version``, ``orders.name``,
  ``instances.label``, ``vouchers.original_id``, ``vouchers.export_photo_id``.
* ``company_settings.iban_encrypted`` → ``iban`` (verschlüsselt war nie etwas).

Revision ID: 176
Revises: 175
"""

from alembic import op

revision = "176"
down_revision = "175"
branch_labels = None
depends_on = None

DEAD_ACTIVE = (
    "ai_memory", "article_process_steps", "articles", "attachments", "captures",
    "document_links", "document_signatures", "documents", "instance_units", "instances",
    "newsletter_consents", "order_lines", "order_units", "orders", "process_steps",
    "recording_chunks", "time_contracts", "time_entries", "user_profiles", "voucher_documents",
    "voucher_entries", "vouchers", "webauthn_challenges",
)

COLUMNS = (
    ("attachments", "created_by"), ("document_refs", "created_by"),
    ("document_links", "created_by"), ("holidays", "created_by"), ("captures", "captured_by"),
    ("articles", "process_version"), ("process_steps", "source_version"), ("orders", "name"),
    ("instances", "label"), ("vouchers", "original_id"), ("vouchers", "export_photo_id"),
)


def upgrade() -> None:
    for table in DEAD_ACTIVE:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS is_active")
    for table, column in COLUMNS:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")
    op.execute("ALTER TABLE company_settings RENAME COLUMN iban_encrypted TO iban")


def downgrade() -> None:
    raise RuntimeError("Aufräumen geht nur vorwärts.")
