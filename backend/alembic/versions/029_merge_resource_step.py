"""consume/tool wieder zu EINEM resource-Schritt zusammenführen (Modus pro Zeile).

Kehrt Migration 028 um: die beiden Schritttypen ``consume``/``tool`` werden zu einem
``resource``-Schritt; der Modus wandert in jede Zeile (``mode='consume'`` bzw.
``'tool'``). Engine behält consume/tool als Alt-Aliase, daher ist dies primär eine
Aufräum-/Normalisierungs-Migration.

Revision ID: 029
Revises: 028
Create Date: 2026-06-24
"""
from alembic import op
from sqlalchemy import inspect

revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, 'article_process_steps'):
        return
    for old, mode in (("consume", "consume"), ("tool", "tool")):
        op.execute(
            f"""
            UPDATE article_process_steps SET step_type='resource',
              resource_lines = COALESCE((
                  SELECT jsonb_agg((e - 'mode') || jsonb_build_object('mode', '{mode}'))
                  FROM jsonb_array_elements(resource_lines) e), resource_lines)
            WHERE step_type='{old}'
            """
        )


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if not _has_table(insp, 'article_process_steps'):
        return
    # resource-Schritte wieder aufteilen: alle-tool → tool, sonst → consume.
    op.execute(
        """
        UPDATE article_process_steps SET step_type='tool'
        WHERE step_type='resource' AND resource_lines IS NOT NULL
          AND jsonb_typeof(resource_lines) = 'array' AND jsonb_array_length(resource_lines) > 0
          AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(resource_lines) e
                          WHERE COALESCE(e->>'mode','consume') = 'consume')
        """
    )
    op.execute("UPDATE article_process_steps SET step_type='consume' WHERE step_type='resource'")
