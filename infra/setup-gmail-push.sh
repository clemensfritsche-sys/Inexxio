#!/usr/bin/env bash
# ►►► Gmail meldet neue Mails selbst – einmal je Projekt einrichten (Cloud Shell, idempotent). ◄◄◄
#
#   bash infra/setup-gmail-push.sh PROJEKT
#   z. B. bash infra/setup-gmail-push.sh inexxio-dev
#
# Voraussetzung: der Takt ist eingerichtet (infra/setup-takt.sh) – die Meldung nutzt sein
# Dienstkonto und seine Zielgruppe (backend/app/core/oidc.py), kein zweiter Weg.
#
# Was es tut (ein zweiter Lauf schadet nicht):
#   1. Pub/Sub einschalten.
#   2. Thema inexxio-mail anlegen; Gmail (gmail-api-push@system.gserviceaccount.com) darf
#      darauf veröffentlichen – nur auf diesem Thema.
#   3. Abo inexxio-mail-push: Pub/Sub ruft POST <Dienst>/api/v1/mail/push, angemeldet mit dem
#      Google-Token von inexxio-tick@PROJEKT (Zielgruppe wie der Takt); Bestätigung bis 60 s,
#      Meldungen höchstens einen Tag aufbewahrt (danach holt sowieso der Takt ab).
#
# Danach meldet sich jedes verbundene Postfach beim nächsten Takt bei Gmail an (mailbox.watch).
# Kosten ≈ 0: Pub/Sub ist bis 10 GB im Monat frei, eine Meldung ist wenige hundert Bytes.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Aufruf: bash infra/setup-gmail-push.sh PROJEKT" >&2
  exit 2
fi

P="$1"
REGION="europe-west6"
TOPIC="inexxio-mail"
SUB="inexxio-mail-push"
TICK="inexxio-tick@$P.iam.gserviceaccount.com"

case "$P" in
  inexxio-dev)  SERVICE="inexxio-backend-dev";  AUDIENCE="inexxio-tick-dev" ;;
  inexxio-prod) SERVICE="inexxio-backend-prod"; AUDIENCE="inexxio-tick-prod" ;;
  *) SERVICE="${SERVICE:?Unbekanntes Projekt – SERVICE=<Cloud-Run-Dienst> setzen}"
     AUDIENCE="${AUDIENCE:?AUDIENCE=<Zielgruppe des Takts> setzen}" ;;
esac

echo "1/3 Pub/Sub einschalten …"
gcloud services enable pubsub.googleapis.com --project "$P"

echo "2/3 Thema $TOPIC – Gmail darf veröffentlichen …"
if ! gcloud pubsub topics describe "$TOPIC" --project "$P" >/dev/null 2>&1; then
  gcloud pubsub topics create "$TOPIC" --project "$P"
fi
gcloud pubsub topics add-iam-policy-binding "$TOPIC" --project "$P" \
  --member "serviceAccount:gmail-api-push@system.gserviceaccount.com" \
  --role "roles/pubsub.publisher" >/dev/null

echo "3/3 Abo $SUB → Dienst $SERVICE …"
URL=$(gcloud run services describe "$SERVICE" --project "$P" --region "$REGION" \
  --format 'value(status.url)')
ENDPOINT="$URL/api/v1/mail/push"
if gcloud pubsub subscriptions describe "$SUB" --project "$P" >/dev/null 2>&1; then
  gcloud pubsub subscriptions update "$SUB" --project "$P" --push-endpoint "$ENDPOINT" \
    --push-auth-service-account "$TICK" --push-auth-token-audience "$AUDIENCE" \
    --ack-deadline 60 --message-retention-duration 1d
else
  gcloud pubsub subscriptions create "$SUB" --project "$P" --topic "$TOPIC" \
    --push-endpoint "$ENDPOINT" --push-auth-service-account "$TICK" \
    --push-auth-token-audience "$AUDIENCE" --ack-deadline 60 --message-retention-duration 1d
fi

echo "Fertig: $ENDPOINT. Beim nächsten Takt meldet sich jedes verbundene Postfach bei Gmail an."
