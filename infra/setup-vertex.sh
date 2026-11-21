#!/usr/bin/env bash
# ►►► Bedeutungs-Zahlen für das Lernen der KI – einmal je Projekt einrichten (Cloud Shell). ◄◄◄
#
#   bash infra/setup-vertex.sh PROJEKT
#   z. B. bash infra/setup-vertex.sh inexxio-dev
#
# Was es tut (ein zweiter Lauf schadet nicht):
#   1. Vertex AI einschalten (aiplatform.googleapis.com).
#   2. Das Konto des Backends (cloudrun-backend@PROJEKT) darf Modelle von Vertex AI aufrufen
#      (roles/aiplatform.user) – angemeldet über das Konto des Dienstes selbst, ohne Schlüssel.
#
# Genutzt wird nur das Hilfsmodell für Bedeutungs-Zahlen (gemini-embedding-001, Region
# europe-west3, Frankfurt): Eingaben werden nicht zum Training verwendet. Kosten: Rappen im
# Monat (0.15 USD je Million Tokens). Ohne diese Einrichtung geht alles – nur ähnliche Fälle
# fehlen der KI (backend/app/services/memory.py).

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Aufruf: bash infra/setup-vertex.sh PROJEKT" >&2
  exit 2
fi

P="$1"
SA="cloudrun-backend@$P.iam.gserviceaccount.com"
say() { printf '\n── %s\n' "$*"; }

say "Vertex AI einschalten ($P)"
gcloud services enable aiplatform.googleapis.com --project "$P"

say "Konto $SA darf Vertex AI aufrufen"
gcloud projects add-iam-policy-binding "$P" --member "serviceAccount:$SA" \
  --role roles/aiplatform.user --condition=None --format='value(etag)'

say "Fertig. Beim nächsten Deploy setzt der Ablauf VERTEX_PROJECT=$P – dann lernt die KI aus ähnlichen Fällen."
