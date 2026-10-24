"""Mehr-Prozess-Modell: Prozesse je Artikel + Standardprozesse, Subjekt-Quelle,
Verkaufs-Schritt und wiederkehrende Vorgänge.

Ein Artikel kann mehrere benannte Prozesse haben (Entstehung, Verkauf, Wartung …);
Schritte gehören zu einem Prozess. Ein Auftrag wählt einen Prozess + Subjekt
(Artikel/Instanz). Neu: ``sales`` (Verkaufs-Schritt) und ``recurring_orders``
(wiederkehrende Vorgänge / Compliance + Abos).

Revision ID: 025
Revises: 024
Create Date: 2026-06-23
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # 1) Prozesse (Artikel-eigen + globale Standardprozesse)
    if not _has_table(insp, 'processes'):
        op.create_table(
            'processes',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True, unique=True),
            sa.Column('article_id', sa.BigInteger(), nullable=True, index=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('source', sa.String(length=20), nullable=False, server_default='produce'),
            sa.Column('is_standard', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='released'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        )
        op.create_index('ix_processes_object_id', 'processes', ['object_id'])

    # 2) Schritte gehören zu einem Prozess; article_id wird nullable (Standardprozesse)
    if not _has_col(insp, 'article_process_steps', 'process_id'):
        op.add_column('article_process_steps', sa.Column('process_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_aps_process_id', 'article_process_steps', ['process_id'])
    try:
        op.alter_column('article_process_steps', 'article_id', nullable=True)
    except Exception:
        pass

    # 3) Auftrag: gewählter Prozess + Subjekt-Instanz
    if not _has_col(insp, 'orders', 'process_id'):
        op.add_column('orders', sa.Column('process_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_orders_process_id', 'orders', ['process_id'])
    if not _has_col(insp, 'orders', 'subject_instance_id'):
        op.add_column('orders', sa.Column('subject_instance_id', sa.BigInteger(), nullable=True))

    # 4) Bestands-Subjekte je Auftrag (Verkauf/Entnahme – Quelle stock)
    if not _has_col(insp, 'instances', 'subject_of_order_id'):
        op.add_column('instances', sa.Column('subject_of_order_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_instances_subject_of_order', 'instances', ['subject_of_order_id'])

    # 5) Bewegung: Sendungsverfolgung (Versand zum Kunden)
    if not _has_col(insp, 'movements', 'tracking_number'):
        op.add_column('movements', sa.Column('tracking_number', sa.String(length=100), nullable=True))
    if not _has_col(insp, 'movements', 'carrier'):
        op.add_column('movements', sa.Column('carrier', sa.String(length=60), nullable=True))

    # 6) Verkaufs-Schritt (Spiegel der Beschaffung, ohne eigene Objektnummer)
    if not _has_table(insp, 'sales'):
        op.create_table(
            'sales',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('order_id', sa.BigInteger(), nullable=False, index=True),
            sa.Column('article_id', sa.BigInteger(), nullable=False, index=True),
            sa.Column('quantity', sa.BigInteger(), nullable=False),
            sa.Column('step_id', sa.BigInteger(), nullable=True, index=True),
            sa.Column('customer_id', sa.BigInteger(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='requested'),
            sa.Column('order_total', sa.Numeric(12, 2), nullable=True),
            sa.Column('vat_rate', sa.Numeric(5, 2), nullable=True),
            sa.Column('currency', sa.String(length=3), nullable=False, server_default='CHF'),
            sa.Column('invoice_number', sa.String(length=60), nullable=True),
            sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('invoiced_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        )

    # 7) Wiederkehrende Vorgänge (Compliance/Termine + Abos)
    if not _has_table(insp, 'recurring_orders'):
        op.create_table(
            'recurring_orders',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('object_id', sa.BigInteger(), nullable=True, unique=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='released'),
            sa.Column('process_id', sa.BigInteger(), nullable=True, index=True),
            sa.Column('article_id', sa.BigInteger(), nullable=True, index=True),
            sa.Column('quantity', sa.Integer(), nullable=True),
            sa.Column('subject_instance_id', sa.BigInteger(), nullable=True),
            sa.Column('interval_days', sa.Integer(), nullable=True),
            sa.Column('lead_time_days', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('validity_days', sa.Integer(), nullable=True),
            sa.Column('next_due_at', sa.Date(), nullable=True),
            sa.Column('valid_until', sa.Date(), nullable=True),
            sa.Column('last_order_id', sa.BigInteger(), nullable=True),
            sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        )

    # 8) Datenmigration: je Artikel mit «losen» Schritten einen Default-«Entstehung»-
    #    Prozess (produce) anlegen, Schritte + bestehende Aufträge daran binden.
    op.execute(
        "INSERT INTO processes (article_id, name, source, is_standard, position, status, "
        "created_at, updated_at, is_active) "
        "SELECT DISTINCT article_id, 'Entstehung', 'produce', false, 1, 'released', "
        "now(), now(), true FROM article_process_steps "
        "WHERE process_id IS NULL AND article_id IS NOT NULL AND is_active = true"
    )
    op.execute(
        "UPDATE article_process_steps s SET process_id = p.id FROM processes p "
        "WHERE s.process_id IS NULL AND s.article_id = p.article_id "
        "AND p.is_standard = false AND p.source = 'produce'"
    )
    op.execute(
        "UPDATE orders o SET process_id = p.id FROM processes p "
        "WHERE o.process_id IS NULL AND o.article_id = p.article_id "
        "AND p.is_standard = false AND p.source = 'produce'"
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table(insp, 'recurring_orders'):
        op.drop_table('recurring_orders')
    if _has_table(insp, 'sales'):
        op.drop_table('sales')
    for idx, table in (('ix_instances_subject_of_order', 'instances'),
                       ('ix_orders_process_id', 'orders'),
                       ('ix_aps_process_id', 'article_process_steps')):
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass
    for table, col in (('movements', 'carrier'), ('movements', 'tracking_number'),
                       ('instances', 'subject_of_order_id'), ('orders', 'subject_instance_id'),
                       ('orders', 'process_id'), ('article_process_steps', 'process_id')):
        if _has_col(insp, table, col):
            op.drop_column(table, col)
    if _has_table(insp, 'processes'):
        op.drop_table('processes')
