#!/usr/bin/env bash
# ►►► Der Takt – einmal je Projekt einrichten (Cloud Shell, idempotent). ◄◄◄
#
#   bash infra/setup-takt.sh PROJEKT DEPLOY-KONTO ALARM-EMAIL
#   z. B. bash infra/setup-takt.sh inexxio-dev github-actions@inexxio-dev.iam.gserviceaccount.com ich@example.com
#
# Was es tut (ein zweiter Lauf schadet nicht, er bringt alles auf denselben Stand):
#   1. Cloud Scheduler einschalten (und seinen Dienst-Agenten anlegen).
#   2. Dienstkonto tick@PROJEKT – es hat KEINE Rolle im Projekt; es darf nur den Backend-Dienst
#      aufrufen (roles/run.invoker auf genau diesem Dienst). Sein Google-Token (OIDC) ist die
#      Anmeldung am Takt; das Backend prüft Konto und Zielgruppe (backend/app/core/oidc.py).
#   3. Das Deploy-Konto darf Scheduler-Jobs verwalten (roles/cloudscheduler.admin) und als
#      tick@ auftreten (roles/iam.serviceAccountUser, nur auf tick@) – den Job selbst legt jeder
#      Deploy an oder führt ihn nach (.github/workflows/deploy.yml, Job «Takt»).
#   4. Alarm: eine log-basierte Kennzahl zählt fehlgeschlagene Aufrufe des Jobs; ab 3 in
#      30 Minuten geht eine Mail an ALARM-EMAIL (Cloud Monitoring).
#
# Der Job selbst entsteht beim nächsten Deploy. Kosten ≈ 0 (infra/README.md, «Der Takt»).

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "Aufruf: bash infra/setup-takt.sh PROJEKT DEPLOY-KONTO ALARM-EMAIL" >&2
  exit 2
fi

P="$1"
DEPLOY_SA="$2"
EMAIL="$3"
REGION="europe-west6"
JOB="inexxio-tick"
TICK="tick@$P.iam.gserviceaccount.com"
METRIC="inexxio-tick-failed"
POLICY_NAME="Inexxio – der Takt scheitert ($P)"
CHANNEL_NAME="Inexxio Alarm ($EMAIL)"

case "$P" in
  inexxio-dev)  SERVICE="inexxio-backend-dev" ;;
  inexxio-prod) SERVICE="inexxio-backend-prod" ;;
  *) SERVICE="${SERVICE:?Unbekanntes Projekt – SERVICE=<Cloud-Run-Dienst> setzen}" ;;
esac

say() { printf '\n── %s\n' "$*"; }

# 1 · Cloud Scheduler ------------------------------------------------------------------
say "Cloud Scheduler einschalten ($P)"
gcloud services enable cloudscheduler.googleapis.com monitoring.googleapis.com \
  logging.googleapis.com --project "$P"
# Der Dienst-Agent stellt die OIDC-Tokens aus; neuere Projekte haben ihn samt Rolle von selbst.
gcloud beta services identity create --service=cloudscheduler.googleapis.com \
  --project "$P" >/dev/null 2>&1 || true

# 2 · Dienstkonto tick@ ----------------------------------------------------------------
say "Dienstkonto $TICK"
if ! gcloud iam service-accounts describe "$TICK" --project "$P" >/dev/null 2>&1; then
  gcloud iam service-accounts create tick --project "$P" \
    --display-name "Inexxio Takt (Cloud Scheduler)" \
    --description "Ruft alle 5 Minuten POST /api/v1/internal/tick – sonst nichts."
fi
gcloud run services add-iam-policy-binding "$SERVICE" --project "$P" --region "$REGION" \
  --member "serviceAccount:$TICK" --role roles/run.invoker --format='value(etag)'

# 3 · Das Deploy-Konto ------------------------------------------------------------------
say "Deploy-Konto $DEPLOY_SA: Scheduler-Jobs verwalten, als tick@ auftreten"
gcloud projects add-iam-policy-binding "$P" --member "serviceAccount:$DEPLOY_SA" \
  --role roles/cloudscheduler.admin --condition=None --format='value(etag)'
gcloud iam service-accounts add-iam-policy-binding "$TICK" --project "$P" \
  --member "serviceAccount:$DEPLOY_SA" --role roles/iam.serviceAccountUser \
  --format='value(etag)'

# 4 · Alarm -----------------------------------------------------------------------------
say "Kennzahl $METRIC (fehlgeschlagene Aufrufe des Jobs $JOB)"
FILTER="resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=\"$JOB\" AND jsonPayload.\"@type\"=\"type.googleapis.com/google.cloud.scheduler.logging.AttemptFinished\" AND severity>=ERROR"
if gcloud logging metrics describe "$METRIC" --project "$P" >/dev/null 2>&1; then
  gcloud logging metrics update "$METRIC" --project "$P" --log-filter "$FILTER" \
    --description "Fehlgeschlagene Aufrufe des Takts ($JOB)"
else
  gcloud logging metrics create "$METRIC" --project "$P" --log-filter "$FILTER" \
    --description "Fehlgeschlagene Aufrufe des Takts ($JOB)"
fi

say "Benachrichtigung per E-Mail an $EMAIL"
CHANNEL=$(gcloud beta monitoring channels list --project "$P" \
  --filter "type=\"email\" AND labels.email_address=\"$EMAIL\"" \
  --format='value(name)' | head -n 1)
if [ -z "$CHANNEL" ]; then
  CHANNEL=$(gcloud beta monitoring channels create --project "$P" \
    --display-name "$CHANNEL_NAME" --type email \
    --channel-labels "email_address=$EMAIL" --format='value(name)')
fi
echo "Kanal: $CHANNEL"

say "Alarm «$POLICY_NAME» (ab 3 Fehlschlägen in 30 Minuten)"
POLICY_FILE=$(mktemp)
trap 'rm -f "$POLICY_FILE"' EXIT
cat > "$POLICY_FILE" <<JSON
{
  "displayName": "$POLICY_NAME",
  "combiner": "OR",
  "enabled": true,
  "notificationChannels": ["$CHANNEL"],
  "documentation": {
    "mimeType": "text/markdown",
    "content": "Cloud Scheduler ruft den Takt (POST /api/v1/internal/tick) alle 5 Minuten; mindestens 3 Aufrufe in 30 Minuten sind gescheitert. Ohne Takt holt und sendet nur das offene ERP Mails, und das Log wird erst beim nächsten Start versiegelt. Nachsehen: Cloud Scheduler → $JOB → Logs; Cloud Run → Logs, Zeilen mit «TICK». infra/README.md, Abschnitt «Der Takt»."
  },
  "conditions": [{
    "displayName": "Der Takt scheitert wiederholt",
    "conditionThreshold": {
      "filter": "metric.type=\"logging.googleapis.com/user/$METRIC\" AND resource.type=\"cloud_scheduler_job\"",
      "aggregations": [{
        "alignmentPeriod": "1800s",
        "perSeriesAligner": "ALIGN_SUM",
        "crossSeriesReducer": "REDUCE_SUM"
      }],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 2,
      "duration": "0s",
      "trigger": { "count": 1 }
    }
  }],
  "alertStrategy": { "autoClose": "86400s" }
}
JSON
POLICY=$(gcloud monitoring policies list --project "$P" \
  --filter "displayName=\"$POLICY_NAME\"" --format='value(name)' | head -n 1)
if [ -n "$POLICY" ]; then
  gcloud monitoring policies update "$POLICY" --project "$P" --policy-from-file "$POLICY_FILE"
else
  gcloud monitoring policies create --project "$P" --policy-from-file "$POLICY_FILE"
fi

say "Fertig. Der Job $JOB entsteht beim nächsten Deploy (Job «Takt»)."
echo "Gegenprobe des Alarms: infra/README.md, Abschnitt «Der Takt»."
