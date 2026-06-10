#!/bin/bash

echo "=== Inexxio Backend Startup ==="
echo "DB revision before upgrade:"
alembic current 2>&1 || echo "(could not read current revision)"

echo "Running Alembic migrations..."
MAX_RETRIES=5
WAIT=3
for i in $(seq 1 $MAX_RETRIES); do
    alembic upgrade head 2>&1
    ALEMBIC_EXIT=$?
    if [ $ALEMBIC_EXIT -eq 0 ]; then
        echo "Migrations completed successfully (attempt $i)."
        break
    fi
    if [ $i -lt $MAX_RETRIES ]; then
        echo "!!! Migration failed (attempt $i/$MAX_RETRIES) — retrying in ${WAIT}s..."
        sleep $WAIT
        WAIT=$((WAIT * 2))
    else
        echo "!!! Migration failed after $MAX_RETRIES attempts — aborting startup."
        alembic current 2>&1 || true
        exit 1
    fi
done

echo "Starting uvicorn on port 8080..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
