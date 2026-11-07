#!/usr/bin/env bash
# ►►► Sprache (Phase 4): das Audio einer Aufnahme bleibt höchstens einen Tag – einmal je Projekt
#     einrichten (Cloud Shell). ◄◄◄
#
#   bash infra/setup-sprache.sh PROJEKT
#   z. B. bash infra/setup-sprache.sh inexxio-dev
#
# Was es tut (ein zweiter Lauf schadet nicht):
#   Im Bucket PROJEKT-files eine Lebensdauer-Regel: Objekte unter «recordings/» werden nach einem
#   Tag gelöscht. Das Backend löscht die Stücke selbst nach der Abschrift und im Takt
#   (backend/app/services/recordings.py); die Regel ist das Netz darunter, falls das einmal
#   scheitert. Vorhandene Regeln (andere Präfixe) bleiben: sie werden gelesen und ergänzt, nie
#   ersetzt. Steht die Regel schon da, ändert sich nichts.
#
# Abschreiben selbst braucht Vertex AI wie die Bedeutungs-Zahlen: einmal infra/setup-vertex.sh.

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Aufruf: bash infra/setup-sprache.sh PROJEKT" >&2
  exit 2
fi

P="$1"
B="gs://$P-files"
say() { printf '\n── %s\n' "$*"; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "Regeln von $B lesen"
gcloud storage buckets describe "$B" --project "$P" --format=json > "$TMP/bucket.json"

# Vorhandene Regeln + unsere – als Lifecycle-Datei. Exit 3: unsere Regel steht schon da.
set +e
python3 - "$TMP/bucket.json" "$TMP/lifecycle.json" <<'PY'
import json
import sys

bucket = json.load(open(sys.argv[1]))
config = bucket.get("lifecycle_config") or bucket.get("lifecycle") or {}
rules = list(config.get("rule") or [])
ours = {"action": {"type": "Delete"}, "condition": {"age": 1, "matchesPrefix": ["recordings/"]}}


def same(rule):
    cond = rule.get("condition") or {}
    return ((rule.get("action") or {}).get("type") == "Delete" and cond.get("age") == 1
            and cond.get("matchesPrefix") == ["recordings/"] and len(cond) == 2)


if any(same(r) for r in rules):
    sys.exit(3)
for r in rules:
    print("  bleibt:", json.dumps(r, ensure_ascii=False))
json.dump({"rule": rules + [ours]}, open(sys.argv[2], "w"), indent=2)
PY
rc=$?
set -e
if [ "$rc" -eq 3 ]; then
  say "Die Regel «recordings/ nach 1 Tag löschen» steht schon – nichts zu tun."
  exit 0
fi
if [ "$rc" -ne 0 ]; then
  echo "Die Regeln von $B liessen sich nicht lesen – abgebrochen, nichts geändert." >&2
  exit 1
fi

say "Regel ergänzen: recordings/ nach 1 Tag löschen"
cat "$TMP/lifecycle.json"
gcloud storage buckets update "$B" --project "$P" --lifecycle-file="$TMP/lifecycle.json"

say "Fertig. Audio liegt in $B höchstens einen Tag (Prüfen: gcloud storage buckets describe $B --format='json(lifecycle_config)')."
