#!/usr/bin/env bash
# =============================================================================
# Inexxio – GCP Infrastructure Setup
# Usage: ./setup.sh <env>
#   env = dev | staging | prod
#
# Prerequisites:
#   - gcloud CLI authenticated (gcloud auth login)
#   - billing account available
#   - firebase CLI installed (npm install -g firebase-tools)
# =============================================================================

set -euo pipefail

# ── Argument validation ──────────────────────────────────────────────────────
ENV="${1:-}"
if [[ "$ENV" != "dev" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <dev|prod>"
  exit 1
fi

# ── Environment-specific configuration ──────────────────────────────────────
REGION="europe-west6"
GCP_PROJECT="inexxio-${ENV}"
FIREBASE_PROJECT="inexxio-${ENV}"
ARTIFACT_REPO="inexxio-${ENV}"
CLOUD_RUN_SERVICE="inexxio-backend-${ENV}"
CLOUD_SQL_INSTANCE="inexxio-${ENV}-db"
GCS_BUCKET="inexxio-${ENV}-storage"
SA_CLOUDRUN="cloudrun-backend@${GCP_PROJECT}.iam.gserviceaccount.com"
SA_GITHUB="github-actions@${GCP_PROJECT}.iam.gserviceaccount.com"
GITHUB_ORG="inexxio"          # Replace with your GitHub org/user
GITHUB_REPO="Inexxio"         # Replace with your GitHub repo name
WI_POOL="github-pool"
WI_PROVIDER="github-provider"

# Cloud SQL tier: db-f1-micro for dev, db-g1-small for staging, db-n1-standard-2 for prod
case "$ENV" in
  dev)     SQL_TIER="db-f1-micro"      ;;
  staging) SQL_TIER="db-g1-small"      ;;
  prod)    SQL_TIER="db-custom-2-7680"  ;;
esac

echo "============================================================"
echo " Inexxio Infrastructure Setup"
echo " Environment : $ENV"
echo " GCP Project : $GCP_PROJECT"
echo " Region      : $REGION"
echo " SQL Tier    : $SQL_TIER"
echo "============================================================"
echo ""

# ── Helper functions ─────────────────────────────────────────────────────────
log()  { echo -e "\n\033[1;34m▶ $*\033[0m"; }
ok()   { echo -e "\033[1;32m  ✓ $*\033[0m"; }
warn() { echo -e "\033[1;33m  ⚠ $*\033[0m"; }

confirm() {
  read -r -p "  Continue? [y/N] " response
  [[ "$response" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
}

# ── 1. Create / link GCP project ─────────────────────────────────────────────
log "Step 1/12 – GCP project"

BILLING_ACCOUNT="01864E-68EB87-B3A4DD"

if gcloud projects describe "$GCP_PROJECT" &>/dev/null; then
  ok "Project $GCP_PROJECT already exists."
else
  gcloud projects create "$GCP_PROJECT" --name="Inexxio ${ENV}" --quiet
  ok "Project $GCP_PROJECT created."
fi

# Always ensure billing is linked (project may exist without billing)
gcloud billing projects link "$GCP_PROJECT" --billing-account="$BILLING_ACCOUNT" --quiet && \
  ok "Billing account linked to $GCP_PROJECT." || \
  warn "Billing may already be linked or requires manual setup."

gcloud config set project "$GCP_PROJECT" --quiet

# ── 2. Enable required GCP APIs ───────────────────────────────────────────────
log "Step 2/12 – Enable GCP APIs (this may take a few minutes)"

APIS=(
  run.googleapis.com
  sqladmin.googleapis.com
  sql-component.googleapis.com
  artifactregistry.googleapis.com
  secretmanager.googleapis.com
  storage.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  cloudresourcemanager.googleapis.com
  firebase.googleapis.com
  identitytoolkit.googleapis.com
  firebasehosting.googleapis.com
)

gcloud services enable "${APIS[@]}" --project="$GCP_PROJECT" --quiet
ok "All APIs enabled."

# ── 3. Artifact Registry ──────────────────────────────────────────────────────
log "Step 3/12 – Artifact Registry"

if gcloud artifacts repositories describe "$ARTIFACT_REPO" \
    --location="$REGION" --project="$GCP_PROJECT" &>/dev/null; then
  ok "Artifact Registry repo $ARTIFACT_REPO already exists."
else
  gcloud artifacts repositories create "$ARTIFACT_REPO" \
    --repository-format=docker \
    --location="$REGION" \
    --description="Docker images for Inexxio ${ENV}" \
    --project="$GCP_PROJECT" \
    --quiet
  ok "Artifact Registry repo $ARTIFACT_REPO created."
fi

# ── 4. Cloud SQL ──────────────────────────────────────────────────────────────
log "Step 4/12 – Cloud SQL PostgreSQL 15"

if gcloud sql instances describe "$CLOUD_SQL_INSTANCE" --project="$GCP_PROJECT" &>/dev/null; then
  ok "Cloud SQL instance $CLOUD_SQL_INSTANCE already exists."
else
  warn "Creating Cloud SQL instance ($SQL_TIER). This takes 5-10 minutes..."

  DELETION_PROTECTION="--deletion-protection"
  if [[ "$ENV" == "dev" ]]; then
    DELETION_PROTECTION="--no-deletion-protection"
  fi

  gcloud sql instances create "$CLOUD_SQL_INSTANCE" \
    --database-version=POSTGRES_15 \
    --tier="$SQL_TIER" \
    --region="$REGION" \
    --storage-type=SSD \
    --storage-size=10GB \
    --storage-auto-increase \
    --backup-start-time=02:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=3 \
    --assign-ip \
    --require-ssl \
    $DELETION_PROTECTION \
    --project="$GCP_PROJECT" \
    --quiet

  # Generate random passwords
  DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
  DB_USER="inexxio"

  gcloud sql databases create inexxio \
    --instance="$CLOUD_SQL_INSTANCE" \
    --project="$GCP_PROJECT" \
    --quiet

  gcloud sql users create "$DB_USER" \
    --instance="$CLOUD_SQL_INSTANCE" \
    --password="$DB_PASSWORD" \
    --project="$GCP_PROJECT" \
    --quiet

  # Store DATABASE_URL in Secret Manager (created in step 7)
  DB_CONNECTION_NAME="${GCP_PROJECT}:${REGION}:${CLOUD_SQL_INSTANCE}"
  DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@/${DB_USER}?host=/cloudsql/${DB_CONNECTION_NAME}"

  ok "Cloud SQL instance $CLOUD_SQL_INSTANCE created."
  ok "Database: inexxio, User: $DB_USER"
  ok "Connection name: $DB_CONNECTION_NAME"
  echo "  DATABASE_URL (save securely): $DATABASE_URL"
fi

# ── 5. GCS Bucket ─────────────────────────────────────────────────────────────
log "Step 5/12 – Google Cloud Storage bucket"

if gsutil ls -b "gs://${GCS_BUCKET}" &>/dev/null; then
  ok "GCS bucket $GCS_BUCKET already exists."
else
  gsutil mb \
    -p "$GCP_PROJECT" \
    -l "$REGION" \
    -b on \
    "gs://${GCS_BUCKET}"

  # Prevent public access
  gsutil ubla set on "gs://${GCS_BUCKET}"

  # Lifecycle: delete incomplete multipart uploads after 7 days
  cat > /tmp/lifecycle.json << 'LIFECYCLE'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "AbortIncompleteMultipartUpload"},
        "condition": {"age": 7}
      }
    ]
  }
}
LIFECYCLE
  gsutil lifecycle set /tmp/lifecycle.json "gs://${GCS_BUCKET}"
  rm /tmp/lifecycle.json

  ok "GCS bucket gs://${GCS_BUCKET} created with uniform access and lifecycle policy."
fi

# ── 6. Service accounts ────────────────────────────────────────────────────────
log "Step 6/12 – Service accounts"

# 6a. Cloud Run service account
if gcloud iam service-accounts describe "$SA_CLOUDRUN" --project="$GCP_PROJECT" &>/dev/null; then
  ok "Service account $SA_CLOUDRUN already exists."
else
  gcloud iam service-accounts create "cloudrun-backend" \
    --display-name="Cloud Run Backend – ${ENV}" \
    --description="Runtime SA for inexxio-backend Cloud Run service in ${ENV}" \
    --project="$GCP_PROJECT" \
    --quiet
  ok "Service account $SA_CLOUDRUN created."
fi

# 6b. GitHub Actions service account
if gcloud iam service-accounts describe "$SA_GITHUB" --project="$GCP_PROJECT" &>/dev/null; then
  ok "Service account $SA_GITHUB already exists."
else
  gcloud iam service-accounts create "github-actions" \
    --display-name="GitHub Actions – ${ENV}" \
    --description="Used by GitHub Actions to deploy to ${ENV} via Workload Identity" \
    --project="$GCP_PROJECT" \
    --quiet
  ok "Service account $SA_GITHUB created."
fi

# ── 7. IAM bindings ───────────────────────────────────────────────────────────
log "Step 7/12 – IAM role bindings"

# Cloud Run SA roles
CLOUDRUN_ROLES=(
  roles/cloudsql.client
  roles/secretmanager.secretAccessor
  roles/storage.objectAdmin
)
for ROLE in "${CLOUDRUN_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
    --member="serviceAccount:${SA_CLOUDRUN}" \
    --role="$ROLE" \
    --condition=None \
    --quiet 2>/dev/null | grep -E "^(Updated|Binding)" || true
done
ok "Cloud Run SA roles granted."

# GitHub Actions SA roles
GITHUB_ROLES=(
  roles/run.admin
  roles/artifactregistry.writer
  roles/iam.serviceAccountUser
  roles/firebase.admin
  roles/storage.admin
)
for ROLE in "${GITHUB_ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
    --member="serviceAccount:${SA_GITHUB}" \
    --role="$ROLE" \
    --condition=None \
    --quiet 2>/dev/null | grep -E "^(Updated|Binding)" || true
done
ok "GitHub Actions SA roles granted."

# ── 8. Workload Identity Federation ───────────────────────────────────────────
log "Step 8/12 – Workload Identity Federation for GitHub Actions"

PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT" --format="value(projectNumber)")

# Create pool
if gcloud iam workload-identity-pools describe "$WI_POOL" \
    --location=global --project="$GCP_PROJECT" &>/dev/null; then
  ok "Workload Identity Pool $WI_POOL already exists."
else
  gcloud iam workload-identity-pools create "$WI_POOL" \
    --location=global \
    --display-name="GitHub Actions Pool – ${ENV}" \
    --description="Allows GitHub Actions to authenticate to GCP without keys" \
    --project="$GCP_PROJECT" \
    --quiet
  ok "Workload Identity Pool $WI_POOL created."
fi

# Create provider
if gcloud iam workload-identity-pools providers describe "$WI_PROVIDER" \
    --workload-identity-pool="$WI_POOL" \
    --location=global --project="$GCP_PROJECT" &>/dev/null; then
  ok "Workload Identity Provider $WI_PROVIDER already exists."
else
  gcloud iam workload-identity-pools providers create-oidc "$WI_PROVIDER" \
    --workload-identity-pool="$WI_POOL" \
    --location=global \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
    --attribute-condition="assertion.repository_owner == '${GITHUB_ORG}'" \
    --project="$GCP_PROJECT" \
    --quiet
  ok "Workload Identity Provider $WI_PROVIDER created."
fi

# Allow the GitHub repo to impersonate the GitHub Actions SA
POOL_RESOURCE="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WI_POOL}/providers/${WI_PROVIDER}"
gcloud iam service-accounts add-iam-policy-binding "$SA_GITHUB" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WI_POOL}/attribute.repository/${GITHUB_ORG}/${GITHUB_REPO}" \
  --project="$GCP_PROJECT" \
  --quiet 2>/dev/null | grep -E "^(Updated|Binding)" || true

ok "Workload Identity binding created."
echo ""
echo "  Add this to your GitHub Actions workflow:"
echo "  workload_identity_provider: ${POOL_RESOURCE}"
echo "  service_account: ${SA_GITHUB}"

# ── 9. Secret Manager secrets ─────────────────────────────────────────────────
log "Step 9/12 – Secret Manager secrets"

SECRETS=(
  DATABASE_URL
  FIREBASE_PROJECT_ID
  SECRET_KEY
  GCS_BUCKET
  CLAUDE_API_KEY
  STRIPE_SECRET_KEY
  STRIPE_WEBHOOK_SECRET
)

for SECRET_NAME in "${SECRETS[@]}"; do
  if gcloud secrets describe "$SECRET_NAME" --project="$GCP_PROJECT" &>/dev/null; then
    ok "Secret $SECRET_NAME already exists."
  else
    # Create secret with a placeholder value – replace via console or gcloud
    case "$SECRET_NAME" in
      DATABASE_URL)
        PLACEHOLDER="postgresql+asyncpg://inexxio:CHANGE_ME@/inexxio?host=/cloudsql/${GCP_PROJECT}:${REGION}:${CLOUD_SQL_INSTANCE}"
        ;;
      FIREBASE_PROJECT_ID)
        PLACEHOLDER="$FIREBASE_PROJECT"
        ;;
      GCS_BUCKET)
        PLACEHOLDER="$GCS_BUCKET"
        ;;
      SECRET_KEY)
        # Generate a real random key for SECRET_KEY
        PLACEHOLDER=$(openssl rand -hex 32)
        ;;
      *)
        PLACEHOLDER="CHANGE_ME"
        ;;
    esac

    printf '%s' "$PLACEHOLDER" | gcloud secrets create "$SECRET_NAME" \
      --data-file=- \
      --replication-policy=user-managed \
      --locations="$REGION" \
      --project="$GCP_PROJECT" \
      --quiet
    ok "Secret $SECRET_NAME created."
  fi
done

# Grant Secret Manager access to Cloud Run SA
gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member="serviceAccount:${SA_CLOUDRUN}" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None \
  --quiet 2>/dev/null | grep -E "^(Updated|Binding)" || true

ok "Secret Manager access granted to Cloud Run SA."

# ── 10. Cloud Run service (initial placeholder) ────────────────────────────────
log "Step 10/12 – Cloud Run service (initial setup)"

if gcloud run services describe "$CLOUD_RUN_SERVICE" \
    --region="$REGION" --project="$GCP_PROJECT" &>/dev/null; then
  ok "Cloud Run service $CLOUD_RUN_SERVICE already exists."
else
  warn "Creating initial Cloud Run service with placeholder image."
  warn "The real image will be deployed by GitHub Actions on first push."

  # Use a minimal hello-world image as placeholder
  gcloud run deploy "$CLOUD_RUN_SERVICE" \
    --image="us-docker.pkg.dev/cloudrun/container/hello" \
    --project="$GCP_PROJECT" \
    --region="$REGION" \
    --platform=managed \
    --no-allow-unauthenticated \
    --service-account="$SA_CLOUDRUN" \
    --add-cloudsql-instances="${GCP_PROJECT}:${REGION}:${CLOUD_SQL_INSTANCE}" \
    --set-env-vars="ENVIRONMENT=${ENV},GCP_PROJECT=${GCP_PROJECT}" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest,FIREBASE_PROJECT_ID=FIREBASE_PROJECT_ID:latest,SECRET_KEY=SECRET_KEY:latest,GCS_BUCKET=GCS_BUCKET:latest" \
    --quiet

  ok "Cloud Run service $CLOUD_RUN_SERVICE created (placeholder image)."
fi

# ── 11. Firebase Hosting setup ────────────────────────────────────────────────
log "Step 11/12 – Firebase project check"

warn "Firebase Hosting must be enabled manually in the Firebase Console:"
echo "  1. Go to https://console.firebase.google.com/project/${FIREBASE_PROJECT}"
echo "  2. Add Firebase to the project if not already done"
echo "  3. Enable Firebase Hosting"
echo "  4. Enable Firebase Authentication (Email/Link + Google provider)"
echo "  5. Run: firebase use ${FIREBASE_PROJECT}"
echo "  6. Run: firebase deploy --only hosting --project ${FIREBASE_PROJECT}"

# ── 12. Summary ───────────────────────────────────────────────────────────────
log "Step 12/12 – Setup complete"

echo ""
echo "============================================================"
echo " Infrastructure for environment: $ENV"
echo "============================================================"
echo ""
echo " GCP Project         : $GCP_PROJECT"
echo " Region              : $REGION"
echo " Artifact Registry   : ${REGION}-docker.pkg.dev/${GCP_PROJECT}/${ARTIFACT_REPO}"
echo " Cloud SQL           : ${GCP_PROJECT}:${REGION}:${CLOUD_SQL_INSTANCE}"
echo " Cloud Run           : $CLOUD_RUN_SERVICE"
echo " GCS Bucket          : gs://${GCS_BUCKET}"
echo " Cloud Run SA        : $SA_CLOUDRUN"
echo " GitHub Actions SA   : $SA_GITHUB"
echo " WI Pool             : $WI_POOL"
echo " WI Provider         : $WI_PROVIDER"
echo ""
echo " Next steps:"
echo " 1. Update Secret Manager secrets with real values:"
echo "    gcloud secrets versions add DATABASE_URL --data-file=- --project=$GCP_PROJECT"
echo " 2. Complete Firebase setup in the console (see step 11 above)"
ENV_UPPER=$(echo "$ENV" | tr '[:lower:]' '[:upper:]')
echo " 3. Add GitHub secret WIF_PROVIDER_${ENV_UPPER}:"
echo "    Value: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WI_POOL}/providers/${WI_PROVIDER}"
echo "    And: WIF_SA_${ENV_UPPER} = $SA_GITHUB"
echo " 4. Push to the develop branch to trigger CI/CD"
echo ""
