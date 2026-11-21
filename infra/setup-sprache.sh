#!/usr/bin/env bash
# ►►► Sprache (Phase 4): ein eigener Bucket für die Stücke einer Aufnahme – das Audio bleibt
#     höchstens einen Tag und ist dann wirklich weg. Einmal je Projekt (Cloud Shell). ◄◄◄
#
#   bash infra/setup-sprache.sh PROJEKT
#   z. B. bash infra/setup-sprache.sh inexxio-dev
#
# Was es tut (ein zweiter Lauf schadet nicht):
#   1. Bucket PROJEKT-recordings (europe-west6) anlegen, falls er fehlt: privat (öffentlicher
#      Zugriff verhindert, uniform access) und OHNE Soft Delete – gelöschtes Audio bleibt nicht
#      eine Woche wiederherstellbar liegen. Steht er schon, werden diese Einstellungen gesetzt.
#   2. Lebensdauer-Regel: jedes Objekt nach einem Tag gelöscht. Das Backend löscht die Stücke
#      selbst nach der Abschrift und im Takt (backend/app/services/recordings.py); die Regel ist
#      das Netz darunter.
#   3. Recht für den Dienst: cloudrun-backend@ bekommt roles/storage.objectAdmin NUR auf diesem
#      Bucket.
#   4. Aufräumen: eine frühere Regel «recordings/ nach 1 Tag» im Datei-Bucket PROJEKT-files fällt
#      weg (Aufnahmen liegen nie dort; die übrigen Regeln bleiben, Soft Delete dort bleibt für
#      die Dokumente).
#
# Der Deploy setzt RECORDINGS_BUCKET=PROJEKT-recordings. Fehlt der Bucket noch, liegen die Stücke
# in der Datenbank (recording_chunks.data) – nichts geht verloren, nur nie im Datei-Bucket.
# Abschreiben selbst braucht Vertex AI wie die Bedeutungs-Zahlen: einmal infra/setup-vertex.sh.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Aufruf: bash infra/setup-sprache.sh PROJEKT" >&2
  exit 2
fi

P="$1"
B="gs://$P-recordings"
FILES="gs://$P-files"
SA="cloudrun-backend@$P.iam.gserviceaccount.com"
say() { printf '\n── %s\n' "$*"; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if gcloud storage buckets describe "$B" --project "$P" --format='value(name)' >/dev/null 2>&1; then
  say "$B steht – privat, ohne Soft Delete setzen"
  gcloud storage buckets update "$B" --project "$P" --clear-soft-delete \
    --uniform-bucket-level-access --public-access-prevention
else
  say "$B anlegen (europe-west6, privat, ohne Soft Delete)"
  gcloud storage buckets create "$B" --project "$P" --location europe-west6 \
    --uniform-bucket-level-access --public-access-prevention --soft-delete-duration=0
fi

say "Lebensdauer: jedes Objekt nach einem Tag löschen"
cat > "$TMP/lifecycle.json" <<'JSON'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 1}}]}
JSON
gcloud storage buckets update "$B" --project "$P" --lifecycle-file="$TMP/lifecycle.json"

say "Recht: $SA darf Objekte in $B lesen, schreiben, löschen – nur dort"
gcloud storage buckets add-iam-policy-binding "$B" --project "$P" \
  --member="serviceAccount:$SA" --role=roles/storage.objectAdmin >/dev/null

say "Frühere Regel «recordings/» im Datei-Bucket $FILES entfernen (falls da)"
if gcloud storage buckets describe "$FILES" --project "$P" --format=json > "$TMP/files.json" 2>/dev/null; then
  set +e
  python3 - "$TMP/files.json" "$TMP/files-lifecycle.json" <<'PY'
import json
import sys

bucket = json.load(open(sys.argv[1]))
config = bucket.get("lifecycle_config") or bucket.get("lifecycle") or {}
rules = list(config.get("rule") or [])


def ours(rule):
    cond = rule.get("condition") or {}
    return ((rule.get("action") or {}).get("type") == "Delete"
            and cond.get("matchesPrefix") == ["recordings/"])


keep = [r for r in rules if not ours(r)]
if len(keep) == len(rules):
    sys.exit(3)
json.dump({"rule": keep}, open(sys.argv[2], "w"), indent=2)
PY
  rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    if grep -q '"rule": \[\]' "$TMP/files-lifecycle.json"; then
      gcloud storage buckets update "$FILES" --project "$P" --clear-lifecycle
    else
      gcloud storage buckets update "$FILES" --project "$P" --lifecycle-file="$TMP/files-lifecycle.json"
    fi
    echo "  entfernt."
  elif [ "$rc" -eq 3 ]; then
    echo "  keine – nichts zu tun."
  else
    echo "Die Regeln von $FILES liessen sich nicht lesen – dort nichts geändert." >&2
  fi
else
  echo "  $FILES nicht gefunden – nichts zu tun."
fi

say "Fertig. Audio liegt in $B höchstens einen Tag (Prüfen: gcloud storage buckets describe $B --format='json(lifecycle_config,soft_delete_policy)')."
