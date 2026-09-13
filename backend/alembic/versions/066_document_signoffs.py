"""Dokument-Freigabe-Parteien (Unterschriften-/Bestätigungs-Layer) + Anerkennungs-Publikum.

* Tabelle ``document_signoffs`` – die endliche Liste der Freigabe-Parteien eines Dokuments
  (append-only Layer: bestätigen ODER unterschreiben; erst wenn ALLE signiert haben, ist das
  Dokument freigegeben und der Auftrag abgeschlossen).
* ``documents.issued`` (BOOL) – Inhalt festgeschrieben (unveränderliche Basis), getrennt von
  ``done`` (= zusätzlich alle Parteien signiert). Backfill: ``issued = done`` (ein ausgestelltes
  Alt-Dokument war ohne Parteien sofort freigegeben).
* ``article_process_steps`` Dokument-Deklaration: ``doc_signers`` (geordnete Parteien),
  ``sign_sequential`` (Reihenfolge erzwingen), ``doc_audience``/``doc_audience_roles``/
  ``doc_audience_person_ids`` (offenes Anerkennungs-Publikum), ``doc_visibility`` (Sichtbarkeit).

Rein additiv (neue Spalten nullable/mit Default, neue Tabelle) – keine Änderung bestehender
Spalten, kein Datenverlust.

Revision ID: 066
Revises: 065
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '066'
down_revision = '065'
branch_labels = None
depends_on = None


def _add(insp, table: str, col: str, type_, **kw) -> None:
    if table in insp.get_table_names():
        if col not in {c["name"] for c in insp.get_columns(table)}:
            op.add_column(table, sa.Column(col, type_, **kw))


def upgrade() -> None:
    insp = inspect(op.get_bind())

    # ── documents.issued (Inhalt eingefroren, getrennt von done = vollständig freigegeben) ──
    _add(insp, "documents", "issued", sa.Boolean(), nullable=False, server_default=sa.text("false"))
    if "documents" in insp.get_table_names():
        # Ein bereits ausgestelltes Alt-Dokument (done) war ohne Parteien sofort freigegeben.
        op.execute("UPDATE documents SET issued = true WHERE done = true")

    # ── Dokument-Deklaration am Prozessschritt ────────────────────────────────────
    _add(insp, "article_process_steps", "doc_signers", JSONB(), nullable=True)
    _add(insp, "article_process_steps", "sign_sequential", sa.Boolean(),
         nullable=False, server_default=sa.text("false"))
    _add(insp, "article_process_steps", "doc_audience", sa.String(length=16), nullable=True)
    _add(insp, "article_process_steps", "doc_audience_roles", JSONB(), nullable=True)
    _add(insp, "article_process_steps", "doc_audience_person_ids", JSONB(), nullable=True)
    _add(insp, "article_process_steps", "doc_visibility", sa.String(length=16),
         nullable=False, server_default=sa.text("'internal'"))

    # ── Tabelle document_signoffs ─────────────────────────────────────────────────
    if "document_signoffs" not in insp.get_table_names():
        op.create_table(
            "document_signoffs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("document_id", sa.BigInteger(), nullable=False),
            sa.Column("order_id", sa.BigInteger(), nullable=False),
            sa.Column("signer_object_id", sa.BigInteger(), nullable=False),
            sa.Column("action", sa.String(length=10), nullable=False, server_default="sign"),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
            sa.Column("signature_url", sa.String(length=300), nullable=True),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acted_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_document_signoffs_document_id", "document_signoffs", ["document_id"])
        op.create_index("ix_document_signoffs_order_id", "document_signoffs", ["order_id"])
        op.create_index("ix_document_signoffs_signer_object_id", "document_signoffs", ["signer_object_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "document_signoffs" in insp.get_table_names():
        op.drop_table("document_signoffs")
    for col in ("doc_signers", "sign_sequential", "doc_audience", "doc_audience_roles",
                "doc_audience_person_ids", "doc_visibility"):
        if "article_process_steps" in insp.get_table_names() and \
                col in {c["name"] for c in insp.get_columns("article_process_steps")}:
            op.drop_column("article_process_steps", col)
    if "documents" in insp.get_table_names() and \
            "issued" in {c["name"] for c in insp.get_columns("documents")}:
        op.drop_column("documents", "issued")
