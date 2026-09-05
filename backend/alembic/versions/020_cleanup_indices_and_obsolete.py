"""Aufräumen: obsolete Spalte inspections.values entfernen + fehlende Indizes
(audit_log.object_id/table_name, claims.order_object_id, instances.location_id).

Revision ID: 020
Revises: 019
Create Date: 2026-06-19
"""
from alembic import op
from sqlalchemy import inspect

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def _columns(bind, table: str) -> set:
    return {c['name'] for c in inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set:
    return {i['name'] for i in inspect(bind).get_indexes(table)}


def _add_index(bind, name: str, table: str, col: str) -> None:
    if _has_table(bind, table) and col in _columns(bind, table) and name not in _indexes(bind, table):
        op.create_index(name, table, [col], unique=False)


def upgrade() -> None:
    bind = op.get_bind()

    # Obsolete Datenerfassungs-Spalte (durch `samples` ersetzt)
    if _has_table(bind, 'inspections') and 'values' in _columns(bind, 'inspections'):
        op.execute('ALTER TABLE inspections DROP COLUMN IF EXISTS "values"')

    # Fehlende Indizes
    _add_index(bind, 'ix_audit_log_object_id', 'audit_log', 'object_id')
    _add_index(bind, 'ix_audit_log_table_name', 'audit_log', 'table_name')
    _add_index(bind, 'ix_claims_order_object_id', 'claims', 'order_object_id')
    _add_index(bind, 'ix_instances_location_id', 'instances', 'location_id')


def downgrade() -> None:
    bind = op.get_bind()
    for name, table in (
        ('ix_audit_log_object_id', 'audit_log'),
        ('ix_audit_log_table_name', 'audit_log'),
        ('ix_claims_order_object_id', 'claims'),
        ('ix_instances_location_id', 'instances'),
    ):
        if _has_table(bind, table) and name in _indexes(bind, table):
            op.drop_index(name, table_name=table)
    # `values` wird nicht wiederhergestellt (Altformat, ungenutzt).
