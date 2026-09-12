#!/usr/bin/env bash
# Vollständiger Dump (Schema + Daten) der Cloud-SQL-Dev-Datenbank.
#
# Zweck: Rollback-Punkt vor einem Umbau. Der Dump gehört NICHT ins Repository
# (er enthält Geschäftsdaten) – .gitignore hält backups/*.sql draussen.
#
# Voraussetzungen: gcloud angemeldet, Leserecht auf das Secret DATABASE_URL,
# pg_dump >= 15 lokal vorhanden.
#
# Aufruf (aus Google Cloud Shell oder einer angemeldeten lokalen Shell):
#   ./scripts/dump-db.sh                 # -> backups/<heute>_pre-refactor.sql
#   ./scripts/dump-db.sh mein-name       # -> backups/<heute>_mein-name.sql
#
# Das Skript bricht bei jedem fehlenden Baustein mit klarer Ursache ab.
# Es gibt keine Fallbacks und keinen Teil-Dump.

set -euo pipefail

PROJECT=inexxio-dev
REGION=europe-west6
DB_INSTANCE=inexxio-dev-db
DB_NAME=inexxio_dev
DB_USER=backend

LABEL="${1:-pre-refactor}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$REPO_ROOT/backups"
OUT_FILE="$OUT_DIR/$(date +%Y%m%d)_${LABEL}.sql"

fail() { echo "ABBRUCH: $*" >&2; exit 1; }

command -v gcloud >/dev/null || fail "gcloud nicht gefunden. Ohne gcloud gibt es keinen Zugang zum Secret und keinen Proxy."
command -v pg_dump >/dev/null || fail "pg_dump nicht gefunden (postgresql-client installieren)."

echo "=== DATABASE_URL aus Secret Manager holen ==="
DATABASE_URL="$(gcloud secrets versions access latest --secret=DATABASE_URL --project "$PROJECT")" \
  || fail "Secret DATABASE_URL nicht lesbar (Projekt $PROJECT). Rechte prüfen."
[ -n "$DATABASE_URL" ] || fail "Secret DATABASE_URL ist leer."

# Passwort steht zwischen '://<user>:' und dem letzten '@'. Kein Raten: passt das
# Muster nicht, bricht das Skript ab, statt mit einem falschen Passwort weiterzulaufen.
DB_PASSWORD="$(printf '%s' "$DATABASE_URL" | sed -nE 's#^[^:]+://[^:]+:(.*)@[^@]*$#\1#p')"
[ -n "$DB_PASSWORD" ] || fail "Passwort liess sich aus DATABASE_URL nicht lesen. Format unerwartet."

echo "=== Cloud SQL Auth Proxy starten ==="
PROXY_BIN=/tmp/cloud_sql_proxy
if [ ! -x "$PROXY_BIN" ]; then
  curl -fsSL https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -o "$PROXY_BIN" \
    || fail "Cloud SQL Proxy nicht herunterladbar."
  chmod +x "$PROXY_BIN"
fi

"$PROXY_BIN" -instances="${PROJECT}:${REGION}:${DB_INSTANCE}=tcp:5433" &
PROXY_PID=$!
trap 'kill "$PROXY_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5433 -U "$DB_USER" -d "$DB_NAME" -c 'SELECT 1' >/dev/null 2>&1 && break
  sleep 1
done
PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5433 -U "$DB_USER" -d "$DB_NAME" -c 'SELECT 1' >/dev/null \
  || fail "Keine Verbindung über den Proxy zu ${PROJECT}:${REGION}:${DB_INSTANCE}/${DB_NAME}."

mkdir -p "$OUT_DIR"
echo "=== Dump nach $OUT_FILE ==="
PGPASSWORD="$DB_PASSWORD" pg_dump \
  -h 127.0.0.1 -p 5433 -U "$DB_USER" -d "$DB_NAME" \
  --format=plain --no-owner --no-privileges \
  --file="$OUT_FILE" \
  || fail "pg_dump fehlgeschlagen. Unvollständige Datei bitte löschen: $OUT_FILE"

echo "=== Fertig ==="
echo "Datei:      $OUT_FILE"
echo "Groesse:    $(du -h "$OUT_FILE" | cut -f1)"
echo "Alembic:    $(PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5433 -U "$DB_USER" -d "$DB_NAME" -tAc 'SELECT version_num FROM alembic_version')"
echo "Zurueckspielen: psql ... -f $OUT_FILE  (in eine LEERE Datenbank)"
