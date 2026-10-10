"""Objektnummern über eine race-sichere Postgres-Sequence (object_id_seq).

Ersetzt die ``max(object_id)+1``-Vergabe. Die Sequence wird angelegt und einmalig
an die höchste bereits vergebene Objektnummer ausgerichtet (rewind-sicher).

Revision ID: 021
Revises: 020
Create Date: 2026-06-19
"""
from alembic import op
from sqlalchemy import inspect

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None

OBJ_ID_START = 100_000_001
SEQ = "object_id_seq"

# Objektnummer-Spalten je Tabelle (eigenständige Objekte mit Nummer).
_TABLES = ("user_profiles", "articles", "orders", "instances", "storage_locations", "claims")


def upgrade() -> None:
    bind = op.get_bind()
    op.execute(
        f"CREATE SEQUENCE IF NOT EXISTS {SEQ} AS BIGINT "
        f"START WITH {OBJ_ID_START} MINVALUE {OBJ_ID_START}"
    )
    # Höchste vergebene Nummer über alle vorhandenen Objekttabellen ermitteln …
    existing = [t for t in _TABLES if inspect(bind).has_table(t)]
    if not existing:
        return
    union = " UNION ALL ".join(f"SELECT MAX(object_id) AS m FROM {t}" for t in existing)
    max_id = bind.exec_driver_sql(f"SELECT MAX(m) FROM ({union}) s").scalar()
    # … und die Sequence darauf heben (nie unter den aktuellen Stand rewinden).
    if max_id is not None and max_id >= OBJ_ID_START:
        op.execute(
            f"SELECT setval('{SEQ}', GREATEST((SELECT last_value FROM {SEQ}), {int(max_id)}), true)"
        )


def downgrade() -> None:
    op.execute(f"DROP SEQUENCE IF EXISTS {SEQ}")
