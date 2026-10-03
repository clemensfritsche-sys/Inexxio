"""Prozess-Objekt entfernen: Prozess hängt am Artikel ODER am Auftrag.

Kein eigenständiges Prozess-Objekt mehr (keine Objektnummer, kein Lebenszyklus,
keine n:m-Verknüpfung). Ein Schritt hängt an ``article_id`` (Artikel-Prozess, «wie
etwas entsteht») oder an ``order_id`` (individueller Auftrags-Prozess). Der Auftrag
trägt einen ``mode`` (make | custom) statt einer Prozesswahl/Subjekt-Instanz.

Kein Rückwärtskompatibilitäts-Aufwand (bewusst): Tabellen ``processes`` und
``article_process_links`` werden verworfen; Altschritte verlieren ``process_id``.

Revision ID: 031
Revises: 030
Create Date: 2026-06-26
"""
from alembic import op
from sqlalchemy import inspect

revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def _cols(insp, table: str) -> set[str]:
    return {c['name'] for c in insp.get_columns(table)} if table in insp.get_table_names() else set()


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())

    # Auftrags-Modus + Schritt-Anker am Auftrag.
    ocols = _cols(insp, 'orders')
    if 'orders' in tables and 'mode' not in ocols:
        op.execute("ALTER TABLE orders ADD COLUMN mode VARCHAR(10) NOT NULL DEFAULT 'make'")
    scols = _cols(insp, 'article_process_steps')
    if 'article_process_steps' in tables and 'order_id' not in scols:
        op.execute("ALTER TABLE article_process_steps ADD COLUMN order_id BIGINT")
        op.execute("CREATE INDEX IF NOT EXISTS ix_aps_order_id ON article_process_steps (order_id)")

    # Obsolete Spalten/Tabellen verwerfen.
    for col in ('process_id', 'subject_instance_id'):
        if col in ocols:
            op.execute(f"ALTER TABLE orders DROP COLUMN {col}")
    if 'process_id' in scols:
        op.execute("ALTER TABLE article_process_steps DROP COLUMN process_id")
    op.execute("DROP TABLE IF EXISTS article_process_links")
    op.execute("DROP TABLE IF EXISTS processes")


def downgrade() -> None:
    # Bewusst nicht umkehrbar (kein Back-Compat): die alten Prozess-Objekte/Links
    # lassen sich nicht rekonstruieren. Spalten wiederherstellen, ohne Daten.
    insp = inspect(op.get_bind())
    ocols = _cols(insp, 'orders')
    scols = _cols(insp, 'article_process_steps')
    if 'orders' in insp.get_table_names():
        if 'process_id' not in ocols:
            op.execute("ALTER TABLE orders ADD COLUMN process_id BIGINT")
        if 'subject_instance_id' not in ocols:
            op.execute("ALTER TABLE orders ADD COLUMN subject_instance_id BIGINT")
        if 'mode' in ocols:
            op.execute("ALTER TABLE orders DROP COLUMN mode")
    if 'article_process_steps' in insp.get_table_names():
        if 'process_id' not in scols:
            op.execute("ALTER TABLE article_process_steps ADD COLUMN process_id BIGINT")
        if 'order_id' in scols:
            op.execute("ALTER TABLE article_process_steps DROP COLUMN order_id")
