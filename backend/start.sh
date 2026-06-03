#!/bin/bash
set -e

echo "[startup] Running Alembic migrations..."
alembic upgrade head

echo "[startup] Starting uvicorn on port 8080..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 2 \
  --loop uvloop \
  --http httptools \
  --log-level info \
  --no-access-log
