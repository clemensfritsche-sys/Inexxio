"""Basis: das Schema auf dem Stand von Migration 161 – eine Datei statt 161.

Die einzelnen Schritte bis 161 sind zusammengefasst; ihre Geschichte steht in git. Eine
Datenbank, die schon auf 161 steht, ist damit «aktuell» und bekommt nichts; eine leere
bekommt das ganze Schema aus ``161_baseline.sql`` (eingefroren aus ``pg_dump``, nie von
Hand ändern). Die nächste Änderung ist Migration 162.

Revision ID: 161
Revises: (keine)
"""

from pathlib import Path

from alembic import op

revision = "161"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    # Über den DBAPI-Cursor ohne Parameter: das SQL enthält ``%`` (in RAISE-Texten) und
    # ``:`` – weder psycopg2 noch SQLAlchemy dürfen darin Platzhalter suchen.
    op.get_bind().connection.dbapi_connection.cursor().execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("Die Basis wird nicht zurückgenommen.")
