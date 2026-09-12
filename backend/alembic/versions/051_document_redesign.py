"""Dokument-Redesign: keine Typ-Trennung mehr, Dokument im Auftrag verfasst.

Ändert:
  • ``articles.physical`` entfernt (keine physisch/nicht-physisch-Trennung mehr – ob ein Dokument
    entsteht, entscheidet allein der Prozessschritt «document»).
  • ``articles.size`` / ``articles.weight_kg`` → nullable (optionale physische Attribute).
  • ``articles.unit`` / ``articles.serialization`` bekommen einen Server-Default (Stk / unit).
  • ``documents``: eigene Objektnummer/Version/Titel/Ausstellungszeit/Nachfolger ENTFERNT (Nummer =
    Instanz-Objektnummer, Datum = Instanz-Freigabe, keine Revisionen). Neu ``done`` – das Dokument
    wird während der Auftragsausführung verfasst und mit «Ausstellen» abgeschlossen.
  • ``article_process_steps.document_content`` entfernt (keine Vorlage mehr; Inhalt kommt im Auftrag).

Revision ID: 051
Revises: 050
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '051'
down_revision = '050'
branch_labels = None
depends_on = None


def _has_column(insp, table, col) -> bool:
    return table in insp.get_table_names() and col in {c["name"] for c in insp.get_columns(table)}


def _drop_index_if_exists(insp, table, name) -> None:
    if table in insp.get_table_names() and name in {i["name"] for i in insp.get_indexes(table)}:
        op.drop_index(name, table_name=table)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # ── Artikel: Typ-Flag weg, physische Attribute optional, Defaults für Einheit/Serialisierung
    if _has_column(insp, "articles", "physical"):
        op.drop_column("articles", "physical")
    if _has_column(insp, "articles", "size"):
        op.alter_column("articles", "size", existing_type=sa.String(length=100), nullable=True)
    if _has_column(insp, "articles", "weight_kg"):
        op.alter_column("articles", "weight_kg", existing_type=sa.Numeric(12, 3), nullable=True)
    if _has_column(insp, "articles", "unit"):
        op.alter_column("articles", "unit", existing_type=sa.String(length=10),
                        server_default="Stk", existing_nullable=False)
    if _has_column(insp, "articles", "serialization"):
        op.alter_column("articles", "serialization", existing_type=sa.String(length=20),
                        server_default="unit", existing_nullable=False)

    # ── Dokument-Vorlage am Schritt entfällt (Inhalt wird im Auftrag verfasst)
    if _has_column(insp, "article_process_steps", "document_content"):
        op.drop_column("article_process_steps", "document_content")

    # ── documents: Fachzeile ohne eigene Nummer/Version; neu ``done``
    if "documents" in insp.get_table_names():
        if not _has_column(insp, "documents", "done"):
            op.add_column("documents", sa.Column(
                "done", sa.Boolean(), nullable=False, server_default=sa.false()))
            # Bestehende Dokumente wurden im Alt-Modell bei der Freigabe eingefroren
            # (= ausgestellt) → als ``done`` markieren, damit ihr Schritt nicht wieder
            # als offen erscheint. Neue Zeilen starten per Default false.
            op.execute("UPDATE documents SET done = true")
        _drop_index_if_exists(insp, "documents", "ix_documents_object_id")
        for col in ("object_id", "version", "title", "issued_at", "replaced_by_id"):
            if _has_column(insp, "documents", col):
                op.drop_column("documents", col)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    # Best-effort-Rückbau (die Alt-Semantik wird nicht wiederhergestellt).
    if "documents" in insp.get_table_names():
        for col, coltype, kw in (
            ("object_id", sa.BigInteger(), {"nullable": True}),
            ("title", sa.String(length=255), {"nullable": True}),
            ("version", sa.Integer(), {"nullable": False, "server_default": "1"}),
            ("issued_at", sa.DateTime(timezone=True), {"nullable": True}),
            ("replaced_by_id", sa.BigInteger(), {"nullable": True}),
        ):
            if not _has_column(insp, "documents", col):
                op.add_column("documents", sa.Column(col, coltype, **kw))
        if _has_column(insp, "documents", "done"):
            op.drop_column("documents", "done")
    if not _has_column(insp, "article_process_steps", "document_content"):
        from sqlalchemy.dialects import postgresql
        op.add_column("article_process_steps", sa.Column(
            "document_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if not _has_column(insp, "articles", "physical"):
        op.add_column("articles", sa.Column(
            "physical", sa.Boolean(), nullable=False, server_default=sa.true()))
