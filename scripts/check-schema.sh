#!/bin/bash
# ►►► Steht die Datenbank nach dem Deploy auf dem Stand des Codes? ◄◄◄
#
# Scheitert `alembic upgrade head` beim Start (backend/start.sh), läuft der Dienst trotzdem
# weiter – die Netze tragen. So blieb die Kette auf dev wochenlang stehen, ohne dass es jemand
# sah. Dieser Schritt liest `/health` (`schema`, `revision`, `head`) und macht den Deploy rot,
# wenn sie nicht übereinstimmen – mit den letzten Zeilen des Starts (der Fehler der Migration).
#
#   scripts/check-schema.sh <Projekt> <Dienst> <Region>
set -u
PROJECT=$1 SERVICE=$2 REGION=$3
URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" \
      --format 'value(status.url)')
# Ein privater Dienst (prod) braucht ein Identitäts-Token; ein öffentlicher (dev) nimmt es auch.
TOKEN=$(gcloud auth print-identity-token --audiences="$URL" 2>/dev/null || true)
BODY=""
for _ in 1 2 3 4 5 6; do
  if [ -n "$TOKEN" ]; then
    BODY=$(curl -sS --max-time 20 -H "Authorization: Bearer $TOKEN" "$URL/health" || true)
  else
    BODY=$(curl -sS --max-time 20 "$URL/health" || true)
  fi
  echo "$BODY" | jq -e '.schema' >/dev/null 2>&1 && break
  sleep 10
done
echo "health: $BODY"
STATE=$(echo "$BODY" | jq -r '.schema // empty' 2>/dev/null || true)
if [ "$STATE" = "current" ]; then
  echo "Die Datenbank steht auf dem Stand des Codes ($(echo "$BODY" | jq -r .revision))."
  exit 0
fi
if [ -z "$STATE" ]; then
  echo "::warning::Den Stand der Datenbank konnte der Deploy nicht lesen (/health ohne Antwort) – bitte von Hand prüfen."
  exit 0
fi
echo "::error::Die Datenbank steht auf $(echo "$BODY" | jq -r .revision) statt $(echo "$BODY" | jq -r .head) – eine Migration ist beim Start gescheitert. Die Zeilen des Starts:"
if LOGS=$(gcloud logging read "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE\"" \
     --project "$PROJECT" --freshness 20m --limit 150 --format 'value(textPayload)' 2>&1) && [ -n "$LOGS" ]; then
  echo "$LOGS" | tac
else
  echo "(Die Logs sind für das Deploy-Konto nicht lesbar – Cloud Run → $SERVICE → Logs. $LOGS)"
fi
exit 1
