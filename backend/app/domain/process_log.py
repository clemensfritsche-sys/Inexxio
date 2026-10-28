"""**Der Ereignis-Log ist append-only – und das steht in der Datenbank.**

Der Log (``process_events``) ist die Quelle der Wahrheit des Prozesses: Bild, Protokoll,
Stückliste und Journey sind Ableitungen aus ihm. Eine Zeile, die sich ändern oder
verschwinden kann, machte jede dieser Ableitungen zu einer Behauptung. Darum sitzt der
Schutz **unter** jeder Anwendung – dieselbe Bauart wie ``statuses.terminal_guard_sql`` und
``timekeeping.append_only_sql``: eine Korrektur ist ein neuer Eintrag, nie eine Änderung
des alten. Der Start schreibt den Trigger bei jedem Lauf neu (``main._sync_database_rules``).
"""

APPEND_ONLY_FN = "process_events_append_only"
APPEND_ONLY_TRIGGER = "trg_process_events_append_only"


def append_only_sql() -> str:
    """Funktion und Trigger: jedes ``UPDATE`` und ``DELETE`` auf ``process_events`` wird
    abgewiesen. Idempotent (``CREATE OR REPLACE`` plus ``DROP TRIGGER IF EXISTS``)."""
    return f"""
DO $guard$
BEGIN
  CREATE OR REPLACE FUNCTION {APPEND_ONLY_FN}() RETURNS trigger AS $fn$
  BEGIN
    RAISE EXCEPTION
      'Ereignis-Log: Eintrag % wird nie geändert oder gelöscht – eine Korrektur ist ein '
      'neuer Eintrag.', OLD.id
      USING ERRCODE = 'check_violation';
  END;
  $fn$ LANGUAGE plpgsql;

  DROP TRIGGER IF EXISTS {APPEND_ONLY_TRIGGER} ON process_events;
  CREATE TRIGGER {APPEND_ONLY_TRIGGER}
    BEFORE UPDATE OR DELETE ON process_events
    FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FN}();
END
$guard$;
"""
