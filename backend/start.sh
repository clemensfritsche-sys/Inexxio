#!/bin/bash

echo "=== Inexxio Backend Startup ==="
echo "DB revision before upgrade:"
alembic current 2>&1 || echo "(could not read current revision)"

echo "Running Alembic migrations..."
alembic upgrade head 2>&1
ALEMBIC_EXIT=$?

if [ $ALEMBIC_EXIT -ne 0 ]; then
    echo "!!! Alembic migration failed (exit $ALEMBIC_EXIT) — starting uvicorn anyway so logs are visible"
    alembic current 2>&1 || true
else
    echo "Migrations completed successfully."
fi

echo "Starting uvicorn on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
