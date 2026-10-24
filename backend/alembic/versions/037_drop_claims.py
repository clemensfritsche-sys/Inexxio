"""Reklamation = Abweichung: die eigenständige ``claims``-Tabelle entfällt.

Reklamationen sind kein eigener Objekttyp mehr – eine «Abweichung» ist ein Auftrag mit
``parent_order_id`` (Unter-Auftrag). Diese Migration entfernt die verwaiste ``claims``-
Tabelle und räumt die zugehörigen Objekt-Registry-Einträge (``object_type='claim'``) auf.
Idempotent/best-effort (keine Rückwärtskompatibilität nötig).

Revision ID: 037
Revises: 036
Create Date: 2026-06-28
"""
from alembic import op
from sqlalchemy import inspect, text

revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    # Verwaiste Registry-Einträge der ehemaligen Reklamationen entfernen (Tabelle 'objects').
    if insp.has_table('objects'):
        bind.execute(text("DELETE FROM objects WHERE object_type = 'claim'"))
    # Eigenständige Reklamations-Tabelle löschen (sie hängt an keiner anderen Tabelle).
    if insp.has_table('claims'):
        op.drop_table('claims')


def downgrade() -> None:
    # Bewusst nicht wiederherstellbar – Reklamationen existieren nur noch als Abweichung.
    pass
