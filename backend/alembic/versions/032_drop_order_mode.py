"""Auftrags-Modus-Flag entfernen: die Subjektart wird abgeleitet.

Kein ``orders.mode`` (make | custom) mehr. Die Subjektart eines Auftrags ergibt sich
aus seiner Gestalt (``services/subject.py``): vorgewählte Instanzen (chosen) ≻ eigene
Schritte ohne Auswahl (stock, FIFO ab Lager) ≻ Artikel + Menge ohne eigene Schritte
(produce, erzeugt Instanzen). Damit lässt sich u. a. der Verkauf einheitlich abbilden.

Kein Rückwärtskompatibilitäts-Aufwand (bewusst): die Spalte wird ersatzlos verworfen.

Revision ID: 032
Revises: 031
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    cols = {c['name'] for c in insp.get_columns('orders')} if 'orders' in insp.get_table_names() else set()
    if 'mode' in cols:
        op.drop_column('orders', 'mode')


def downgrade() -> None:
    op.add_column('orders', sa.Column(
        'mode', sa.String(length=10), server_default='make', nullable=False))
