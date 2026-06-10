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
fi

echo "Starting uvicorn on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
