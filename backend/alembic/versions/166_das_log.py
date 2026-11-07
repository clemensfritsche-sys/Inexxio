"""Das Log: eine Tabelle für alles, was geschieht (Projektakte «Die lernende Firma» §1).

* ``log`` – append-only; jede Zeilen-Änderung schreibt die Datenbank selbst hinein, jedes
  fachliche Ereignis ``log_event`` (Funktionen und Trigger schreibt der Start aus
  ``domain/log``, wie die anderen Trigger der Fachschicht).
* ``log_seal`` – je abgeschlossenem Tag eine Prüfsumme, verkettet.
* Die Ereignisse des Prozesses ziehen aus ``process_events`` als ``process.<art>`` ins Log
  um; die Sicht ``process_log`` zeigt sie so, wie Bild, Protokoll, Stückliste und Journey sie
  lesen. ``audit_log`` wird nicht übernommen (keine Rückwärtskompatibilität).
* ``process_events`` und ``audit_log`` bleiben für EINEN Deploy ungemappt stehen
  (Zwei-Deploy-Regel) und gehen mit Migration 167 – die holt vorher nach, was die alte
  Fassung während des Ausrollens noch in ``process_events`` schrieb (``payload.pe`` = die
  alte ``id``). Der Rückbau (``downgrade``) schreibt die neuen Einträge dorthin zurück.

Revision ID: 166
Revises: 165
"""

from alembic import op

revision = "166"
down_revision = "165"
branch_labels = None
depends_on = None

#: Die Sicht des Prozess-Logs – eingefroren hier, nicht aus dem Code gelesen.
PROCESS_LOG_VIEW = """
CREATE VIEW process_log AS
SELECT l.id,
       (l.payload ->> 'order')::bigint AS order_id,
       (l.payload ->> 'step')::bigint  AS step_id,
       (l.payload ->> 'unit')::bigint  AS instance_unit_id,
       substr(l.event, 9) AS kind,
       l.payload ->> 'before' AS status_before,
       l.payload ->> 'after'  AS status_after,
       l.payload -> 'data' AS payload,
       u.id AS actor_id,
       l.at AS created_at
  FROM log l
  LEFT JOIN user_profiles u ON l.actor_kind = 'person' AND u.object_id = l.actor_id
 WHERE l.event LIKE 'process.%'
"""


def upgrade() -> None:
    op.execute("""
CREATE TABLE log (
    id bigserial PRIMARY KEY,
    at timestamptz NOT NULL DEFAULT now(),
    actor_kind varchar(10) NOT NULL,
    actor_id bigint,
    source varchar(12) NOT NULL,
    request_id uuid NOT NULL,
    object_id bigint,
    table_name varchar(64),
    row_key varchar(64),
    action varchar(8) NOT NULL,
    event varchar(64),
    changes jsonb,
    payload jsonb,
    CONSTRAINT ck_log_actor_kind CHECK (actor_kind IN ('person', 'ai', 'system', 'external')),
    CONSTRAINT ck_log_action CHECK (action IN ('insert', 'update', 'delete', 'event')),
    CONSTRAINT ck_log_event CHECK ((action = 'event') = (event IS NOT NULL))
)""")
    op.execute("CREATE INDEX ix_log_object_at ON log (object_id, at)")
    op.execute("CREATE INDEX ix_log_request ON log (request_id)")
    op.execute("CREATE INDEX ix_log_actor_at ON log (actor_id, at)")
    op.execute("CREATE INDEX ix_log_event_at ON log (event, at)")
    op.execute("CREATE INDEX ix_log_at ON log (at)")                    # Siegel je Tag
    # Die Fragen des Prozesses: Geschichte eines Stücks; Ereignisse eines Auftrags und «was
    # geschah an diesem Modul» (Stichprobe, Protokoll) – der zweite Index trägt beide.
    op.execute("CREATE INDEX ix_log_process_unit ON log (((payload ->> 'unit')::bigint), id) "
               "WHERE event LIKE 'process.%'")
    op.execute("CREATE INDEX ix_log_process_step ON log (((payload ->> 'order')::bigint), "
               "((payload ->> 'step')::bigint), substr(event, 9)) WHERE event LIKE 'process.%'")
    op.execute("""
CREATE TABLE log_seal (
    day date PRIMARY KEY,
    first_id bigint,
    last_id bigint,
    entries bigint NOT NULL,
    hash varchar(64) NOT NULL,
    sealed_at timestamptz NOT NULL DEFAULT now()
)""")
    # Die bisherigen Prozess-Ereignisse – in ihrer Reihenfolge, als ein Vorgang.
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
 ORDER BY e.id
""")
    op.execute(PROCESS_LOG_VIEW)


def downgrade() -> None:
    # **Die Historie geht mit zurück**: was seit 166 im Log entstand, kommt in
    # ``process_events`` – sonst fehlten der älteren Fassung die Übergänge, die die Stücke
    # inzwischen gemacht haben. Übernommene Einträge tragen ``pe`` (ihre alte ``id``) und
    # kommen nur dann zurück, wenn ``process_events`` sie nicht mehr hat (nach 167).
    op.execute("""
INSERT INTO process_events (order_id, step_id, instance_unit_id, kind, status_before,
                            status_after, payload, actor_id, created_at)
SELECT p.order_id, p.step_id, p.instance_unit_id, p.kind, p.status_before, p.status_after,
       p.payload, p.actor_id, p.created_at
  FROM process_log p
  JOIN log l ON l.id = p.id
 WHERE NOT EXISTS (SELECT 1 FROM process_events e
                    WHERE e.id = (l.payload ->> 'pe')::bigint)
 ORDER BY p.id
""")
    op.execute("DROP VIEW IF EXISTS process_log")
    for fn in ("log_row()", "log_immutable()", "log_event(text, bigint, jsonb, text, text, "
               "text, bigint)", "log_process(jsonb)", "log_redact(bigint, text)",
               "log_seal_due()", "log_verify()", "log_digest(date)", "log_shorten(jsonb)",
               "log_actor()"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn} CASCADE")
    op.execute("DROP TABLE IF EXISTS log_seal")
    op.execute("DROP TABLE IF EXISTS log")
