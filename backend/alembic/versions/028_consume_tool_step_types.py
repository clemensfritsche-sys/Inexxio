"""consume/tool aus dem Prozessschritt statt Artikel-Art.

Die Unterscheidung Verbrauchsmaterial vs. Betriebsmittel wird NICHT mehr am Artikel
(``articles.kind``) gemacht, sondern ergibt sich aus dem **Schritttyp**: der frühere
``resource``-Schritt wird in zwei Schritttypen aufgeteilt – ``consume`` (Verbrauch,
FIFO/Lagerabgang) und ``tool`` (Betriebsmittel, nur genutzt).

- ``articles.kind`` wird entfernt.
- Bestehende ``resource``-Schritte: reine Betriebsmittel-Schritte (alle Zeilen
  ``mode='tool'``) → ``tool``; alle übrigen → ``consume``.

Revision ID: 028
Revises: 027
Create Date: 2026-06-24
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    insp = inspect(op.get_bind())

    if _has_col(insp, 'articles', 'kind'):
        op.drop_column('articles', 'kind')

    if _has_table(insp, 'article_process_steps'):
        # Reine Betriebsmittel-Schritte (keine consume-Zeile) → tool …
        op.execute(
            """
            UPDATE article_process_steps SET step_type='tool'
            WHERE step_type='resource' AND resource_lines IS NOT NULL
              AND jsonb_typeof(resource_lines) = 'array'
              AND jsonb_array_length(resource_lines) > 0
              AND NOT EXISTS (
                  SELECT 1 FROM jsonb_array_elements(resource_lines) e
                  WHERE COALESCE(e->>'mode', 'consume') = 'consume')
            """
        )
        # … alle übrigen Ressourcen-Schritte → consume (Verbrauch).
        op.execute("UPDATE article_process_steps SET step_type='consume' WHERE step_type='resource'")


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_col(insp, 'articles', 'kind'):
        op.add_column('articles', sa.Column(
            'kind', sa.String(length=20), nullable=False, server_default='material'))
    if _has_table(insp, 'article_process_steps'):
        op.execute(
            "UPDATE article_process_steps SET step_type='resource' WHERE step_type IN ('consume','tool')")
