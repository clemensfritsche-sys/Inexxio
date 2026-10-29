# Infrastruktur – Ist-Stand

> Was hier steht, ist **so eingerichtet**. Massgeblich sind die Workflows
> (`.github/workflows/deploy.yml`, aufgerufen von `deploy-dev.yml` und `deploy-prod.yml` mit
> den Werten ihrer Umgebung) – sie setzen bei jedem Deploy alles, was ein Dienst braucht;
> diese Seite erklärt es nur. Eingerichtet wird nicht per Skript, sondern einmal
> von Hand (unten), und jeder Deploy prüft danach, ob es trägt.

## Zwei Umgebungen

| Umgebung | Branch    | GCP-/Firebase-Projekt | Adresse                       | Freigabe |
|----------|-----------|-----------------------|-------------------------------|----------|
| dev      | `develop` | `inexxio-dev`         | https://inexxio-dev.web.app   | Push     |
| prod     | `main`    | `inexxio-prod`        | https://inexxio-prod.web.app  | Push + Freigabe (Environment `production`) |

Je Umgebung, alles in **europe-west6 (Zürich)**:

- **Frontend + Website**: Firebase Hosting, statischer Export (`firebase.json`). `/api/**`
  geht per Rewrite an den Backend-Dienst; **Firebase Hosting bricht jede Anfrage nach 60 s ab**.
- **Backend**: Cloud Run `inexxio-backend-<env>`, Dienstkonto `cloudrun-backend@<projekt>`.
  `start.sh` fährt bei jedem Start `alembic upgrade head`, dann uvicorn.
- **Datenbank**: Cloud SQL PostgreSQL (`inexxio-dev-db`, Datenbank `inexxio_dev`, Benutzer
  `backend`), angebunden über den Unix-Socket (`--add-cloudsql-instances`).
- **Dateien**: Bucket `<projekt>-files` (privat, `FILES_BUCKET`, `docs/dokumente.md`).
- **Secrets**: Secret Manager, als Umgebungsvariablen eingebunden. Pflicht: `DATABASE_URL`;
  dev ausserdem `FIREBASE_PROJECT_ID` (prod setzt es als Wert). Optional – auf beiden Seiten
  dieselbe Liste, eingebunden nur, wenn es sie gibt: `GOOGLE_CLIENT_ID`/`_SECRET` (Gmail),
  `ANTHROPIC_API_KEY` (KI), `GOOGLE_MAPS_API_KEY` (Adress-Suche), `LINK_SECRET` (signierte
  Links), `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`; `STRIPE_PUBLISHABLE_KEY` auf prod als
  Secret, auf dev als Wert im Workflow (kein Geheimnis). Ein Name bleibt bei seiner Form:
  Cloud Run weist es ab, wenn eine Variable von «Secret» auf «Wert» wechselt. Welche es
  gibt, liest der Deploy aus **einer** Liste (`gcloud secrets list`); dafür braucht das
  Deploy-Konto die Rolle `roles/secretmanager.viewer` (nur Namen, keine Werte). Fehlt ein
  Pflicht-Secret oder ist die Liste nicht lesbar, wird der Deploy rot.
- **Bilder des Backends**: Artifact Registry `europe-west6-docker.pkg.dev/<projekt>/<repo>`.

## Der Ablauf

1. **Das Gate** (`quality.yml`) – auch auf jedem Push eines Feature-Branches und jedem Pull
   Request: Frontend (Typen, Lint, Tests, Build), Backend (ruff, pytest gegen PostgreSQL –
   das Schema bauen die Migrationen –, generierte Dateien) und Website (Tests, Astro,
   Abdrucke, Build) laufen parallel. Aus dem Deploy aufgerufen baut es nicht selbst.
2. Prod: **Freigabe** (Environment `production`).
3. **Build** (`deploy.yml`): Website und Frontend mit den Werten der Umgebung, zusammengeführt
   zur Hosting-Ausgabe (Artefakt); dev mit `X-Robots-Tag: noindex`, prod mit dem
   `/api/**`-Rewrite auf den Prod-Dienst. Scheitert er, ist nichts ausgerollt.
4. **Backend**: Bild bauen (die GeoIP-Tabelle je Monat aus dem Cache), Cloud Run, danach
   **steht die Datenbank auf dem Stand des Codes?** (`scripts/check-schema.sh` liest
   `/health` → `schema`, `revision`, `head`). Sonst rot.
5. **Hosting**: genau die Ausgabe aus 3 nach Firebase Hosting.

Der Dienst ist auf beiden Seiten öffentlich aufrufbar (`--allow-unauthenticated`): Firebase
Hosting leitet `/api/**` nur an einen öffentlichen Dienst weiter; wer etwas darf, prüft das
Backend bei jeder Anfrage selbst.

## Einmal von Hand (je Umgebung)

```bash
P=inexxio-dev   # bzw. inexxio-prod
# Datei-Ablage
gcloud storage buckets create gs://$P-files --project $P --location europe-west6 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding gs://$P-files \
  --member serviceAccount:cloudrun-backend@$P.iam.gserviceaccount.com --role roles/storage.objectAdmin
# ein optionales Secret (z. B. der KI-Schlüssel) – der nächste Deploy bindet es ein
printf '%s' 'WERT' | gcloud secrets create ANTHROPIC_API_KEY --data-file=- --project $P
```

## Betrieb absichern (einmal, in Cloud Shell)

Jeder Block steht für sich; `P` ist das Projekt.

```bash
# 1 · Budget-Alarm (Mail bei 50 / 90 / 100 % des Monatsbudgets) – das Konto zuerst nachsehen
gcloud billing accounts list
gcloud billing budgets create --billing-account=KONTO-ID --display-name="Inexxio" \
  --budget-amount=100 --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0

# 2 · Erreichbarkeit: /health des Backends jede 5 Minuten (503 auch, wenn die Datenbank
#     nicht auf dem Stand des Codes ist). /health liegt am Dienst selbst, nicht hinter /api.
P=inexxio-dev
HOST=$(gcloud run services describe inexxio-backend-dev --region europe-west6 --project $P \
  --format='value(status.url)' | sed 's#https://##')
gcloud monitoring uptime create inexxio-health --project $P \
  --resource-type=uptime-url --resource-labels=host=$HOST,project_id=$P \
  --path=/health --protocol=https --period=5
#   Mail bei Ausfall: Console → Monitoring → Uptime checks → «inexxio-health» →
#   «Create alert» → Benachrichtigung per E-Mail.

# 3 · Prod: tägliche Sicherung + Wiederherstellung auf die Minute (vor dem Go-live)
gcloud sql instances patch inexxio-prod-db --project inexxio-prod \
  --backup-start-time=01:00 --enable-point-in-time-recovery --retained-backups-count=14

# 4 · Alte Backend-Bilder aufräumen: die 10 jüngsten bleiben, der Rest geht nach 30 Tagen
cat > /tmp/policy.json <<'JSON'
[{"name":"keep-recent","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":10}},
 {"name":"delete-old","action":{"type":"Delete"},"condition":{"olderThan":"30d"}}]
JSON
gcloud artifacts repositories set-cleanup-policies $P --project $P \
  --location europe-west6 --policy=/tmp/policy.json

# 5 · Neues Datenbank-Passwort (dev) – setzt es, schreibt es ins Secret, startet neu
NEW=$(openssl rand -hex 24)
gcloud sql users set-password backend --instance inexxio-dev-db --project inexxio-dev --password "$NEW"
gcloud secrets versions access latest --secret DATABASE_URL --project inexxio-dev \
  | sed -E "s#(://backend:)[^@]*@#\1$NEW@#" | tr -d '\n' \
  | gcloud secrets versions add DATABASE_URL --data-file=- --project inexxio-dev
gcloud run services update inexxio-backend-dev --region europe-west6 --project inexxio-dev \
  --update-labels=rotated=$(date +%s)
```

## Anmeldung der Deploys ohne Schlüssel (Workload Identity)

GitHub meldet sich bei Google mit einem kurzlebigen Token an, das nur für dieses Repository
gilt – kein JSON-Schlüssel, der irgendwo liegt. Prod und dev sind so eingerichtet (dev: Oktober 2026); für ein neues Projekt einmal
(idempotent, ein zweiter Lauf schadet nicht):

```bash
P=inexxio-dev; REPO=clemensfritsche-sys/Inexxio; SA=github-actions@$P.iam.gserviceaccount.com
gcloud iam service-accounts describe $SA --project $P --format='value(email)' \
  || gcloud iam service-accounts list --project $P
NUM=$(gcloud projects describe $P --format='value(projectNumber)')
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com --project $P
gcloud iam workload-identity-pools create github --project $P --location global \
  --display-name GitHub 2>/dev/null || true
gcloud iam workload-identity-pools providers create-oidc github --project $P --location global \
  --workload-identity-pool github --display-name GitHub \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping 'google.subject=assertion.sub,attribute.repository=assertion.repository' \
  --attribute-condition "assertion.repository=='$REPO'" 2>/dev/null || true
gcloud iam service-accounts add-iam-policy-binding $SA --project $P \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$NUM/locations/global/workloadIdentityPools/github/attribute.repository/$REPO" \
  --format='value(etag)'
# Der Deploy liest die Namen der Secrets (nicht ihre Werte)
gcloud projects add-iam-policy-binding $P --member serviceAccount:$SA \
  --role roles/secretmanager.viewer --condition=None --format='value(etag)'
echo "PROVIDER=projects/$NUM/locations/global/workloadIdentityPools/github/providers/github"
```

Dev nennt Provider und Konto offen (`deploy-dev.yml`, Eingaben an `deploy.yml`), prod
liest sie aus den Repository-Secrets `WIF_PROVIDER_PROD`/`WIF_SA_PROD` – beides ist kein
Geheimnis; gelten lässt Google es nur für Anfragen aus genau diesem Repository. Danach den
alten Schlüssel löschen (`gcloud iam service-accounts keys list --iam-account $SA
--managed-by=user`, dann `… keys delete <ID> --iam-account $SA`) und in GitHub das Secret
`GCP_SA_KEY_DEV` entfernen.

## Werkzeuge

- `scripts/check-schema.sh` – der Schritt nach dem Deploy (oben).
- `docker-compose.yml` – nur die lokale Datenbank (PostgreSQL 16).
- `scripts/dump-db.sh` – vollständige Sicherung der dev-Datenbank (Cloud Shell).
- `scripts/reset-dev-db.sql` – dev leeren, damit sie neu aus den Migrationen entsteht
  (`backend/CLAUDE.md`). Bricht auf jeder anderen Datenbank ab.

## Logs und Rollback

```bash
gcloud run services logs read inexxio-backend-dev --region europe-west6 --project inexxio-dev
gcloud run revisions list --service inexxio-backend-dev --region europe-west6 --project inexxio-dev
gcloud run services update-traffic inexxio-backend-dev --to-revisions <REVISION>=100 \
  --region europe-west6 --project inexxio-dev
```
Das Frontend kehrt mit einem Revert auf dem Branch zurück. Rollback-Punkte stehen als
Commit-Hash in `docs/history/`.

## Laufende Kosten

> **Die Regel: was nicht auf null skaliert, kostet rund um die Uhr.** Cloud Run tut es
> (ausser mit `--min-instances ≥ 1`), Cloud SQL nie.

Eine ungenutzte Umgebung ist darum nicht gratis, sondern fast so teuer wie eine
benutzte — und genau das ist im Sommer 2026 passiert: `inexxio-prod` wurde am
5. Juni deployt, danach lief die Entwicklung ausschliesslich auf `develop`/dev, und
die Prod-Umgebung rechnete zweieinhalb Monate lang ~108 CHF/Monat ab, ohne dass
jemand sie aufrief. Das waren ~85 % der Gesamtrechnung.

Grössenordnungen in **europe-west6 (Zürich)** — der teuersten EU-Region, ca. 25–35 %
über europe-west1/west4:

| Posten                                   | grob CHF/Monat |
|------------------------------------------|----------------|
| Cloud SQL `db-custom-2-7680` (2 vCPU/7,5 GB) | ~100       |
| Cloud SQL `db-g1-small`                  | ~35            |
| Cloud SQL `db-f1-micro`                  | ~10            |
| Cloud Run, `--min-instances 1`, je Dienst | ~7–9          |
| Cloud Run, `--min-instances 0`, im Leerlauf | ~0          |
| Artifact Registry                        | ~0,2 (1,8 GB)  |
| Firebase Hosting, Secret Manager, GCS    | ~1–2           |

Heute: beide Backends mit `--min-instances 0` (je bis 2 Instanzen, je 1 CPU,
512 MiB, ein Worker). Prod geht beim Go-live auf `min_instances: 1` (`deploy-prod.yml`).
Verbindungen: je Worker bis 5 + 5 (`app/core/database.py`), also höchstens
Instanzen × 10 = 20 – passt ab `db-f1-micro` (25); mehr Instanzen erst ab `db-g1-small` (50).

Daraus die drei Regeln:

1. **Eine Umgebung, die nicht gebraucht wird, wird gestoppt oder gelöscht** — nicht
   «stehen gelassen, kostet ja nichts». Eine gestoppte Cloud-SQL-Instanz
   (`--activation-policy=NEVER`) spart rund 95 %; nur der Speicher läuft weiter.
2. **Klein starten.** Eine Tier-Änderung ist ein Befehl und ein Neustart; zu gross
   zu starten ist ein Dauerauftrag, der niemandem auffällt.
3. **Ein Budget-Alarm ist die einzige Instanz, die es merkt** (siehe «Betrieb absichern»).
