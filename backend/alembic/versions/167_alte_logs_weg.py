"""``audit_log`` und ``process_events`` fallen (Zwei-Deploy-Regel, nach Migration 166).

Seit 166 durch das Log ersetzt und ungemappt; der Deploy mit 166 ist ausgerollt. Mit den
Tabellen gehen ihre Funktion ``process_events_append_only`` und ihre Sequenzen.

Revision ID: 167
Revises: 166
"""

from alembic import op

revision = "167"
down_revision = "166"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Was die alte Fassung während des Ausrollens von 166 noch in ``process_events`` schrieb,
    # kommt vorher ins Log (übernommene Einträge tragen ``payload.pe`` = ihre alte ``id``).
    op.execute("""
INSERT INTO log (at, actor_kind, actor_id, source, request_id, object_id, table_name,
                 row_key, action, event, payload)
SELECT e.created_at,
       CASE WHEN u.object_id IS NULL THEN 'system' ELSE 'person' END,
       u.object_id, 'migration', m.request, o.object_id, 'instance_units',
       e.instance_unit_id::text, 'event', 'process.' || e.kind,
       jsonb_build_object('order', e.order_id, 'unit', e.instance_unit_id,
                          'before', e.status_before, 'after', e.status_after, 'pe', e.id)
       || CASE WHEN e.step_id IS NULL THEN '{}'::jsonb
               ELSE jsonb_build_object('step', e.step_id) END
       || CASE WHEN jsonb_typeof(e.payload) = 'object'
               THEN jsonb_build_object('data', e.payload) ELSE '{}'::jsonb END
  FROM process_events e
  JOIN orders o ON o.id = e.order_id
  LEFT JOIN user_profiles u ON u.id = e.actor_id
  CROSS JOIN (SELECT gen_random_uuid() AS request) m
 WHERE NOT EXISTS (SELECT 1 FROM log l WHERE l.event LIKE 'process.%'
                     AND (l.payload ->> 'pe')::bigint = e.id)
 ORDER BY e.id
""")
    op.execute("DROP TABLE IF EXISTS process_events")
    op.execute("DROP FUNCTION IF EXISTS process_events_append_only()")
    op.execute("DROP TABLE IF EXISTS audit_log")


def downgrade() -> None:
    # Leer zurück – die Inhalte stehen im Log (``process.*``); ``audit_log`` wurde nie übernommen.
    op.execute("""
CREATE TABLE IF NOT EXISTS audit_log (
    id bigserial PRIMARY KEY, object_id bigint, table_name varchar(100) NOT NULL,
    field_name varchar(100), old_value text, new_value text, user_id bigint,
    on_behalf varchar(12), changed_at_utc timestamptz NOT NULL)""")
    op.execute("""
CREATE TABLE IF NOT EXISTS process_events (
    id bigserial PRIMARY KEY, order_id bigint NOT NULL, step_id bigint,
    instance_unit_id bigint NOT NULL, kind varchar(10) NOT NULL,
    status_before varchar(30) NOT NULL, status_after varchar(30) NOT NULL, payload jsonb,
    actor_id bigint, created_at timestamptz NOT NULL DEFAULT now())""")
