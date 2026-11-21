#!/bin/bash
# ►►► **Erst die Datenbank, dann der Dienst – scheitert die Migration, startet er nicht.** ◄◄◄
#
# Cloud Run schaltet den Verkehr nur auf eine Revision, die startet: bricht dieser Start ab,
# bleibt die vorige Revision live, und der Deploy wird rot (scripts/check-schema.sh). Eine
# Revision, die gegen ein halb migriertes Schema läuft, gibt es damit nicht.
#
# Einzige Ausnahme: **die Datenbank ist neuer als dieser Code** («Can't locate revision») –
# das ist eine ältere Revision, die nach einem Rollback oder während eines Rollouts startet.
# Sie darf laufen; das Schema ist eines, das ihr Nachfolger schon kennt.

echo "=== Inexxio Backend Startup ==="

MIGRATION_LOG=/tmp/migration.log

echo "Running Alembic migrations..."
alembic upgrade head > "$MIGRATION_LOG" 2>&1
ALEMBIC_EXIT=$?
cat "$MIGRATION_LOG"

if [ $ALEMBIC_EXIT -ne 0 ]; then
    if grep -q "Can.t locate revision" "$MIGRATION_LOG"; then
        echo "!!! Die Datenbank steht auf einer neueren Revision als dieser Code – gestartet wird"
        echo "!!! trotzdem (Rollback oder Rollout). Gilt das länger, ist der Deploy zu prüfen."
    else
        echo "!!! Alembic migration failed (exit $ALEMBIC_EXIT) – der Dienst startet NICHT."
        exit 1
    fi
fi

WORKERS="${WEB_WORKERS:-2}"
echo "Starting uvicorn on port 8080 with $WORKERS workers..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers "$WORKERS"
