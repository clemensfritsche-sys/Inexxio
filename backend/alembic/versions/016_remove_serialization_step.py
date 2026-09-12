"""Serialisierung als eigener Prozessschritt entfernt – Instanzen entstehen bei Freigabe

Revision ID: 016
Revises: 015
Create Date: 2026-06-18
"""
from alembic import op
from sqlalchemy import inspect

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    # «serialization» ist kein eigener Schritt mehr – Definitionen soft-löschen
    # (kein Hard-Delete). Die Bestands-Instanzen werden bei der Auftragsfreigabe
    # angelegt; der Wareneingang erfolgt über den Beschaffungsschritt («received»).
    if _has_table(bind, 'article_process_steps'):
        op.execute(
            "UPDATE article_process_steps SET is_active=false WHERE step_type='serialization'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'article_process_steps'):
        op.execute(
            "UPDATE article_process_steps SET is_active=true WHERE step_type='serialization'"
        )
