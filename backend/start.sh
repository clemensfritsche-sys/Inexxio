#!/bin/bash

echo "=== Inexxio Backend Startup ==="

MIGRATION_LOG=/tmp/migration.log

echo "Running Alembic migrations..."
alembic upgrade head > "$MIGRATION_LOG" 2>&1
ALEMBIC_EXIT=$?

if [ $ALEMBIC_EXIT -eq 0 ]; then
    echo "Migrations completed successfully."
    cat "$MIGRATION_LOG"
else
    echo "!!! Alembic migration failed (exit $ALEMBIC_EXIT) — starting uvicorn anyway, schema fix will run in lifespan"
    cat "$MIGRATION_LOG"
    alembic current 2>&1 || true
    # **Eine Diagnose, keine Automatik.** Steht die Datenbank auf einer Revision, die
    # dieser Code nicht kennt (typisch nach einem Revert, dessen Downgrade nicht lief),
    # laeuft die App dank Lifespan-Netz weiter — aber KEINE kuenftige Migration mehr.
    # Automatisch zu stampen waere falsch: waehrend eines Rollouts ist ein hoeherer
    # Stand der NORMALFALL, und die alte Revision wuerde die neue zurueckstellen.
    if grep -q "Can.t locate revision" "$MIGRATION_LOG"; then
        echo "!!! ---------------------------------------------------------------"
        echo "!!! Die Datenbank steht auf einer Revision, die dieser Code nicht kennt."
        echo "!!! Die App laeuft (das Netz legt fehlende Spalten an), der Migrations-"
        echo "!!! pfad ist aber blockiert. Behoben mit einem einmaligen"
        echo "!!!     alembic stamp <hoechste Revision in alembic/versions>"
        echo "!!! gegen diese Datenbank, danach laeuft 'upgrade head' wieder."
        echo "!!! ---------------------------------------------------------------"
    fi
fi

echo "Starting uvicorn on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
