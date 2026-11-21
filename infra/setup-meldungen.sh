#!/usr/bin/env bash
# ►►► Meldungen der Stufe ERROR per Mail – einmal je Projekt (Cloud Shell, idempotent). ◄◄◄
#
#   bash infra/setup-meldungen.sh PROJEKT ALARM-EMAIL
#
# Jede Betriebsmeldung des Dienstes geht durch backend/app/core/report.py und trägt ihre Stufe.
# Hier: eine log-basierte Kennzahl zählt die Meldungen der Stufe ERROR des Backend-Dienstes;
# sobald es in 5 Minuten eine gibt, geht eine Mail an ALARM-EMAIL. Kosten ≈ 0.

set -euo pipefail
if [ $# -ne 2 ]; then echo "Aufruf: bash infra/setup-meldungen.sh PROJEKT ALARM-EMAIL" >&2; exit 2; fi
P="$1"; EMAIL="$2"
case "$P" in
  inexxio-dev)  SERVICE="inexxio-backend-dev" ;;
  inexxio-prod) SERVICE="inexxio-backend-prod" ;;
  *) SERVICE="${SERVICE:?Unbekanntes Projekt – SERVICE=<Cloud-Run-Dienst> setzen}" ;;
esac
METRIC="inexxio-errors"
POLICY_NAME="Inexxio – Fehlermeldung des Dienstes ($P)"
FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE\" AND severity>=ERROR"

gcloud services enable monitoring.googleapis.com logging.googleapis.com --project "$P"
if gcloud logging metrics describe "$METRIC" --project "$P" >/dev/null 2>&1; then
  gcloud logging metrics update "$METRIC" --project "$P" --log-filter "$FILTER" --description "Meldungen der Stufe ERROR ($SERVICE)"
else
  gcloud logging metrics create "$METRIC" --project "$P" --log-filter "$FILTER" --description "Meldungen der Stufe ERROR ($SERVICE)"
fi

CHANNEL=$(gcloud beta monitoring channels list --project "$P" \
  --filter "type=\"email\" AND labels.email_address=\"$EMAIL\"" --format='value(name)' | head -n 1)
if [ -z "$CHANNEL" ]; then
  CHANNEL=$(gcloud beta monitoring channels create --project "$P" --display-name "Inexxio Alarm ($EMAIL)" \
    --type email --channel-labels "email_address=$EMAIL" --format='value(name)')
fi

POLICY_FILE=$(mktemp); trap 'rm -f "$POLICY_FILE"' EXIT
cat > "$POLICY_FILE" <<JSON
{
  "displayName": "$POLICY_NAME",
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": ["$CHANNEL"],
  "documentation": {"mimeType": "text/markdown",
    "content": "Der Dienst $SERVICE hat eine Meldung der Stufe ERROR geschrieben (backend/app/core/report.py). Nachsehen: Cloud Run → $SERVICE → Logs, Filter severity=ERROR."},
  "conditions": [{
    "displayName": "Eine Fehlermeldung",
    "conditionThreshold": {
      "filter": "metric.type=\"logging.googleapis.com/user/$METRIC\" AND resource.type=\"cloud_run_revision\"",
      "aggregations": [{"alignmentPeriod": "300s", "perSeriesAligner": "ALIGN_SUM", "crossSeriesReducer": "REDUCE_SUM"}],
      "comparison": "COMPARISON_GT", "thresholdValue": 0, "duration": "0s", "trigger": {"count": 1}
    }
  }],
  "alertStrategy": {"autoClose": "86400s"}
}
JSON
POLICY=$(gcloud beta monitoring policies list --project "$P" --filter "displayName=\"$POLICY_NAME\"" --format='value(name)' | head -n 1)
if [ -n "$POLICY" ]; then
  gcloud beta monitoring policies update "$POLICY" --project "$P" --policy-from-file "$POLICY_FILE"
else
  gcloud beta monitoring policies create --project "$P" --policy-from-file "$POLICY_FILE"
fi
echo "Fertig: Meldungen der Stufe ERROR von $SERVICE gehen an $EMAIL."
