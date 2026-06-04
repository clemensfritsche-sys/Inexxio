#!/usr/bin/env bash
# One-time GCP infrastructure setup for inexxio-dev.
# Run this in Google Cloud Shell: https://shell.cloud.google.com
#
# Usage:
#   chmod +x setup-gcp-dev.sh
#   ./setup-gcp-dev.sh
#
# After this script completes, copy the printed GCP_SA_KEY_DEV JSON
# to GitHub → Settings → Secrets → Actions → New secret: GCP_SA_KEY_DEV

set -euo pipefail

PROJECT=inexxio-dev
REGION=europe-west6
DB_INSTANCE=inexxio-dev-db
DB_NAME=inexxio_dev
DB_USER=backend
ARTIFACT_REPO=inexxio-dev
CLOUD_RUN_SERVICE=inexxio-backend-dev
DEPLOY_SA=deploy-sa
BACKEND_SA=cloudrun-backend

echo "=== [1/9] Enabling GCP APIs ==="
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT" --quiet

echo "=== [2/9] Creating Artifact Registry repository ==="
gcloud artifacts repositories create "$ARTIFACT_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project "$PROJECT" \
  --quiet 2>/dev/null || echo "  (already exists)"

echo "=== [3/9] Creating Cloud SQL instance (takes ~5 min) ==="
gcloud sql instances create "$DB_INSTANCE" \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --project "$PROJECT" \
  --storage-type=SSD \
  --storage-size=10GB \
  --no-backup \
  --quiet 2>/dev/null || echo "  (already exists)"

echo "=== [4/9] Creating database and user ==="
DB_PASSWORD=$(openssl rand -base64 24)

gcloud sql databases create "$DB_NAME" \
  --instance="$DB_INSTANCE" \
  --project "$PROJECT" \
  --quiet 2>/dev/null || echo "  (database already exists)"

gcloud sql users create "$DB_USER" \
  --instance="$DB_INSTANCE" \
  --password="$DB_PASSWORD" \
  --project "$PROJECT" \
  --quiet 2>/dev/null || {
    echo "  (user exists, setting new password)"
    gcloud sql users set-password "$DB_USER" \
      --instance="$DB_INSTANCE" \
      --password="$DB_PASSWORD" \
      --project "$PROJECT" --quiet
  }

DB_CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE" \
  --project "$PROJECT" --format='value(connectionName)')

DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"

echo "=== [5/9] Creating Secret Manager secrets ==="
SECRET_KEY=$(openssl rand -base64 32)

for secret in DATABASE_URL SECRET_KEY FIREBASE_PROJECT_ID INITIAL_ADMIN_EMAIL GCS_BUCKET_NAME; do
  gcloud secrets create "$secret" \
    --replication-policy=automatic \
    --project "$PROJECT" \
    --quiet 2>/dev/null || echo "  (secret $secret already exists)"
done

echo "$DATABASE_URL"  | gcloud secrets versions add DATABASE_URL      --data-file=- --project "$PROJECT"
echo "$SECRET_KEY"    | gcloud secrets versions add SECRET_KEY         --data-file=- --project "$PROJECT"
echo "inexxio-dev"    | gcloud secrets versions add FIREBASE_PROJECT_ID --data-file=- --project "$PROJECT"
echo "clemens.fritsche@gmail.com" | gcloud secrets versions add INITIAL_ADMIN_EMAIL --data-file=- --project "$PROJECT"
echo ""               | gcloud secrets versions add GCS_BUCKET_NAME    --data-file=- --project "$PROJECT"

echo "=== [6/9] Creating Cloud Run runtime service account ==="
gcloud iam service-accounts create "$BACKEND_SA" \
  --display-name="Cloud Run Backend" \
  --project "$PROJECT" \
  --quiet 2>/dev/null || echo "  (already exists)"

BACKEND_SA_EMAIL="${BACKEND_SA}@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/cloudsql.client" --quiet

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" --quiet

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/firebase.sdkAdminServiceAgent" --quiet 2>/dev/null || \
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${BACKEND_SA_EMAIL}" \
  --role="roles/firebaseauth.admin" --quiet 2>/dev/null || true

echo "=== [7/9] Creating deploy service account for GitHub Actions ==="
gcloud iam service-accounts create "$DEPLOY_SA" \
  --display-name="GitHub Actions Deploy" \
  --project "$PROJECT" \
  --quiet 2>/dev/null || echo "  (already exists)"

DEPLOY_SA_EMAIL="${DEPLOY_SA}@${PROJECT}.iam.gserviceaccount.com"

for role in \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/iam.serviceAccountUser \
  roles/cloudsql.client \
  roles/secretmanager.secretAccessor \
  roles/firebasehosting.admin; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="$role" --quiet
done

echo "=== [8/9] Creating deploy SA key (→ add to GitHub Secrets as GCP_SA_KEY_DEV) ==="
gcloud iam service-accounts keys create /tmp/gcp-sa-key-dev.json \
  --iam-account="$DEPLOY_SA_EMAIL" \
  --project "$PROJECT"

echo ""
echo "========================================================="
echo "  GCP_SA_KEY_DEV (copy everything between the lines):"
echo "========================================================="
cat /tmp/gcp-sa-key-dev.json
echo ""
echo "========================================================="

echo "=== [9/9] Initial Cloud Run deploy (placeholder to create the service) ==="
gcloud run deploy "$CLOUD_RUN_SERVICE" \
  --image=gcr.io/cloudrun/hello \
  --project "$PROJECT" \
  --region "$REGION" \
  --platform managed \
  --no-allow-unauthenticated \
  --service-account "${BACKEND_SA_EMAIL}" \
  --add-cloudsql-instances "${DB_CONNECTION_NAME}" \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest,INITIAL_ADMIN_EMAIL=INITIAL_ADMIN_EMAIL:latest" \
  --set-env-vars "APP_ENV=development,CORS_ORIGINS=[\"https://inexxio-dev.web.app\",\"http://localhost:3000\"]" \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60s \
  --concurrency 80 \
  --quiet

echo ""
echo "=== DONE ==="
echo ""
echo "Next steps:"
echo "1. Copy the GCP_SA_KEY_DEV JSON above → GitHub Secrets"
echo "2. Also add FIREBASE_SERVICE_ACCOUNT_INEXXIO_DEV (Firebase Admin SA JSON) → GitHub Secrets"
echo "3. Push to 'develop' branch → GitHub Actions deploys backend + frontend"
echo "4. After first real deploy, run Alembic: scripts/run-migrations.sh"
echo ""
echo "DB connection name: ${DB_CONNECTION_NAME}"
echo "Backend SA: ${BACKEND_SA_EMAIL}"
echo "Deploy SA: ${DEPLOY_SA_EMAIL}"
