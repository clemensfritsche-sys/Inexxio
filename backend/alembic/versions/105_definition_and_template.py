"""Definitionsbereich des Auftrags + Erzeugungsprozess des Artikels.

Zwei neue Tabellen und drei neue Spalten:

``order_lines``            – die Definitionszeilen (Artikel · Menge · Herkunft). Sie
                             halten fest, was der Mensch oberhalb des Start-Symbols
                             eingetragen hat; die **Herkunft** ist danach aus dem
                             Bestand nicht mehr ablesbar.
``article_process_steps``  – der Erzeugungsprozess als **Vorlage**. Eigene Tabelle, weil
                             diese Zeilen nie laufen: was es nicht gibt, kann nicht
                             ausgeführt werden.
``articles.process_version`` – Versionsstempel der Vorlage.
``process_steps.source_*``   – der Stempel auf der **Kopie** im Auftrag.

Die Kopie ist der Punkt: ein Verweis auf die Vorlage hiesse, dass eine spätere
Artikeländerung laufende Aufträge rückwirkend umschreibt.

Revision ID: 105
Revises: 104
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "105"
down_revision = "104"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return bool(
        bind.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).first()
    )


def upgrade() -> None:
    # Idempotent, weil das Lifespan-Sicherheitsnetz dieselben Spalten anlegt, falls
    # Alembic bei einem Deploy scheitert (Lehre aus Migration 090).
    if not _has_column("articles", "process_version"):
        op.add_column(
            "articles",
            sa.Column("process_version", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
        )
    if not _has_column("process_steps", "source_article_id"):
        op.add_column("process_steps", sa.Column("source_article_id", sa.BigInteger(), nullable=True))
    if not _has_column("process_steps", "source_version"):
        op.add_column("process_steps", sa.Column("source_version", sa.Integer(), nullable=True))

    op.execute("DROP TABLE IF EXISTS order_lines CASCADE")
    op.create_table(
        "order_lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])
    op.create_index("ix_order_lines_article_id", "order_lines", ["article_id"])

    op.execute("DROP TABLE IF EXISTS article_process_steps CASCADE")
    op.create_table(
        "article_process_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("module_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status_before", sa.String(30), nullable=False),
        sa.Column("status_after", sa.String(30), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_article_process_steps_article_id", "article_process_steps", ["article_id"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS article_process_steps CASCADE")
    op.execute("DROP TABLE IF EXISTS order_lines CASCADE")
    if _has_column("process_steps", "source_version"):
        op.drop_column("process_steps", "source_version")
    if _has_column("process_steps", "source_article_id"):
        op.drop_column("process_steps", "source_article_id")
    if _has_column("articles", "process_version"):
        op.drop_column("articles", "process_version")
