# Infrastruktur – Ist-Stand

> Was hier steht, ist **so eingerichtet**. Massgeblich sind die Workflows
> (`.github/workflows/deploy-*.yml`) – sie setzen bei jedem Deploy alles, was ein Dienst
> braucht; diese Seite erklärt es nur. Eingerichtet wird nicht per Skript, sondern einmal
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
  dev ausserdem `FIREBASE_PROJECT_ID`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
  Optional – eingebunden nur, wenn es sie gibt: `GOOGLE_CLIENT_ID`/`_SECRET` (Gmail),
  `ANTHROPIC_API_KEY` (KI), `GOOGLE_MAPS_API_KEY` (Adress-Suche), auf prod auch die drei
  Stripe-Werte (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`).
- **Bilder des Backends**: Artifact Registry `europe-west6-docker.pkg.dev/<projekt>/<repo>`.

## Was jeder Deploy prüft

1. Das Gate (`quality.yml`): Typen, Lint, Tests, Build, Schema aus den Migrationen.
2. Nach dem Ausrollen: **steht die Datenbank auf dem Stand des Codes?**
   (`scripts/check-schema.sh` liest `/health` → `schema`, `revision`, `head`). Sonst rot.

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

## Werkzeuge

- `scripts/check-schema.sh` – der Schritt nach dem Deploy (oben).
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
|
