"""Aufgaben (Projektakte «Aufgaben», Runde 1): wer was kann, wer woran ist.

- ``user_profiles.competences`` – Wörter aus ``domain/competences`` (gesetzt vom Admin).
- ``task_focus`` – eine Zeile je Person: ``task_key`` (leer = frei, eindeutig wo gesetzt),
  ``since``, ``handed_key``. Die Aufgabe selbst ist eine Ableitung, nicht gespeichert.

Revision ID: 188
Revises: 187
"""

from alembic import op

revision = "188"
down_revision = "187"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_profiles ADD COLUMN competences TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("""
        CREATE TABLE task_focus (
            person_object_id BIGINT PRIMARY KEY,
            task_key VARCHAR(120),
            since TIMESTAMPTZ NOT NULL,
            handed_key VARCHAR(120),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )""")
    op.execute("CREATE UNIQUE INDEX uq_task_focus_task ON task_focus (task_key) "
               "WHERE task_key IS NOT NULL")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_focus")
    op.execute("ALTER TABLE user_profiles DROP COLUMN IF EXISTS competences")
