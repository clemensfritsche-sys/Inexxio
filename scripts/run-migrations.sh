#!/usr/bin/env bash
# Run Alembic migrations against the Cloud SQL dev database.
# Run this from Google Cloud Shell after first backend deploy.
#
# Usage:
#   chmod +x run-migrations.sh
#   ./run-migrations.sh

set -euo pipefail

PROJECT=inexxio-dev
REGION=europe-west6
DB_INSTANCE=inexxio-dev-db
DB_NAME=inexxio_dev
DB_USER=backend

echo "=== Fetching DATABASE_URL from Secret Manager ==="
DATABASE_URL=$(gcloud secrets versions access latest \
  --secret=DATABASE_URL \
  --project "$PROJECT")

echo "=== Starting Cloud SQL Auth Proxy ==="
wget -q https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O /tmp/cloud_sql_proxy
chmod +x /tmp/cloud_sql_proxy

DB_CONNECTION_NAME="${PROJECT}:${REGION}:${DB_INSTANCE}"
/tmp/cloud_sql_proxy -instances="${DB_CONNECTION_NAME}=tcp:5432" &
PROXY_PID=$!
trap "kill $PROXY_PID 2>/dev/null" EXIT

sleep 2

echo "=== Running Alembic migrations ==="
cd "$(dirname "$0")/../backend"
pip install -r requirements.txt -q

# Convert Unix socket URL to TCP for local proxy
TCP_URL="postgresql+psycopg2://${DB_USER}:$(echo "$DATABASE_URL" | sed 's/.*://' | cut -d@ -f1)@localhost:5432/${DB_NAME}"
DATABASE_URL="$TCP_URL" alembic upgrade head

echo "=== Migrations complete ==="
