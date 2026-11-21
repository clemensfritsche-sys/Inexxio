"""Integrität des Prozesses: Fremdschlüssel, der Log append-only, ein passender Index.

* **Fremdschlüssel** für die Prozesstabellen – jede Zeile zeigt auf etwas, das es gibt.
  ``ON DELETE RESTRICT``: hier wird nicht gelöscht, und ein Versuch scheitert laut statt
  einen Verweis ins Leere zu hinterlassen. Gibt es schon einen Verweis ins Leere, bricht
  diese Migration mit dem Namen der Bedingung ab (die Waisen-Abfrage steht im
  Rundenbericht) – der Dienst bleibt dann auf der alten Revision.
* **``process_events`` append-only** per Trigger (dieselbe Bauart wie die Zeiterfassung);
  der Start schreibt ihn danach bei jedem Lauf neu (``domain/process_log``).
* **Index** ``(order_id, step_id, kind)`` für die Fragen «was ist an diesem Modul
  passiert» (Stichprobe, Protokoll); ``ix_process_events_unit`` fällt weg – er ist der
  Anfang von ``ix_process_events_unit_timeline``.

Revision ID: 163
Revises: 162
"""

from alembic import op

revision = "163"
down_revision = "162"
branch_labels = None
depends_on = None

#: (Tabelle, Spalte, Zieltabelle, Zielspalte) – eingefroren, nicht aus dem Code gelesen.
FOREIGN_KEYS = (
    ("order_lines", "order_id", "orders", "id"),
    ("order_lines", "article_id", "articles", "id"),
    ("order_units", "order_id", "orders", "id"),
    ("order_units", "instance_unit_id", "instance_units", "id"),
    ("order_units", "current_step_id", "process_steps", "id"),
    ("order_units", "return_to_order_id", "orders", "id"),
    ("process_steps", "order_id", "orders", "id"),
    ("process_steps", "source_article_id", "articles", "id"),
    ("process_events", "order_id", "orders", "id"),
    ("process_events", "step_id", "process_steps", "id"),
    ("process_events", "instance_unit_id", "instance_units", "id"),
    ("process_events", "actor_id", "user_profiles", "id"),
    ("captures", "instance_unit_id", "instance_units", "id"),
    ("captures", "order_id", "orders", "id"),
    ("captures", "step_id", "process_steps", "id"),
    ("captures", "captured_by", "user_profiles", "id"),
    ("instance_units", "instance_id", "instances", "id"),
    ("instance_units", "place_unit_id", "instance_units", "id"),
    ("instance_units", "place_object_id", "objects", "object_id"),
)

APPEND_ONLY = """
CREATE OR REPLACE FUNCTION process_events_append_only() RETURNS trigger AS $fn$
BEGIN
  RAISE EXCEPTION
    'Ereignis-Log: Eintrag % wird nie geändert oder gelöscht – eine Korrektur ist ein '
    'neuer Eintrag.', OLD.id
    USING ERRCODE = 'check_violation';
END;
$fn$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS trg_process_events_append_only ON process_events;
CREATE TRIGGER trg_process_events_append_only
  BEFORE UPDATE OR DELETE ON process_events
  FOR EACH ROW EXECUTE FUNCTION process_events_append_only();
"""


def _name(table: str, column: str) -> str:
    return f"fk_{table}_{column}"


def upgrade() -> None:
    for table, column, target, target_column in FOREIGN_KEYS:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {_name(table, column)} "
            f"FOREIGN KEY ({column}) REFERENCES {target} ({target_column}) "
            f"ON DELETE RESTRICT"
        )
    op.execute("CREATE INDEX ix_process_events_order_step_kind "
               "ON process_events (order_id, step_id, kind)")
    op.execute("DROP INDEX IF EXISTS ix_process_events_unit")
    # Über den DBAPI-Cursor ohne Parameter: der RAISE-Text enthält ``%``.
    op.get_bind().connection.dbapi_connection.cursor().execute(APPEND_ONLY)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_process_events_append_only ON process_events")
    op.execute("DROP FUNCTION IF EXISTS process_events_append_only()")
    op.execute("CREATE INDEX ix_process_events_unit ON process_events (instance_unit_id)")
    op.execute("DROP INDEX IF EXISTS ix_process_events_order_step_kind")
    for table, column, _target, _col in reversed(FOREIGN_KEYS):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {_name(table, column)}")
