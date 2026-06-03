# Inexxio – Infrastructure & Deployment

## Overview

Inexxio runs on Google Cloud Platform (europe-west6 / Zurich) with three isolated environments:

| Environment | Branch    | GCP Project       | Firebase Project   | Domain                  |
|-------------|-----------|-------------------|--------------------|-------------------------|
| dev         | develop   | inexxio-dev       | inexxio-dev        | inexxio.web.app         |
| staging     | staging   | inexxio-staging   | inexxio-staging    | inexxio-staging.web.app |
| prod        | main      | inexxio-prod      | inexxio-prod       | inexxio.com             |

## Architecture

```
GitHub Actions
      │
      ├── push develop  →  deploy-dev.yml
      ├── push staging  →  deploy-staging.yml
      └── push main     →  deploy-prod.yml (+ manual approval)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
           Firebase Hosting          Cloud Run (backend)
           (Next.js SSR)             (FastAPI + uvicorn)
                    │                       │
                    │                  Cloud SQL (PostgreSQL 15)
                    │                  Secret Manager
                    │                  Cloud Storage
                    └────── API calls via /api/** rewrite ──────►
```

### Components per environment

- **Frontend**: Firebase Hosting with Web Frameworks (Next.js SSR). Region: europe-west6.
- **Backend**: Cloud Run (managed), no public unauthenticated access. Firebase Hosting rewrites `/api/**` to the Cloud Run service.
- **Database**: Cloud SQL PostgreSQL 15 via Unix socket (`/cloudsql/PROJECT:REGION:INSTANCE`). No public IP.
- **Secrets**: All sensitive config lives in Secret Manager. Cloud Run injects them as environment variables at startup.
- **Storage**: GCS bucket with uniform bucket-level access, no public access.
- **Auth**: Firebase Authentication (Magic Link + Google SSO). Admin requires TOTP MFA.

---

## Initial Setup

### Prerequisites

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud auth application-default login

# Install Firebase CLI
npm install -g firebase-tools
firebase login
```

### Provision a new environment

```bash
cd infra/
chmod +x setup.sh

# For development environment
./setup.sh dev

# For staging
./setup.sh staging

# For production (prompts for confirmation)
./setup.sh prod
```

The script creates (idempotent – safe to re-run):
1. GCP project with billing
2. All required APIs enabled
3. Artifact Registry Docker repository
4. Cloud SQL PostgreSQL 15 instance
5. GCS storage bucket
6. Cloud Run service accounts with least-privilege IAM
7. Workload Identity Federation pool + provider (no service account keys needed)
8. Secret Manager secrets (placeholder values – update before first deploy)
9. Cloud Run service (placeholder image)

### After running setup.sh

**1. Update secrets with real values:**

```bash
ENV=dev   # or staging / prod
PROJECT="inexxio-${ENV}"

# Database URL (automatically set during setup for new instances)
# If you need to update it:
echo -n "postgresql+asyncpg://inexxio:PASSWORD@/inexxio?host=/cloudsql/${PROJECT}:europe-west6:inexxio-${ENV}-db" \
  | gcloud secrets versions add DATABASE_URL --data-file=- --project=$PROJECT

# Firebase project ID (auto-set to inexxio-${ENV} by setup.sh)

# Claude API key
echo -n "sk-ant-..." | gcloud secrets versions add CLAUDE_API_KEY --data-file=- --project=$PROJECT

# Stripe (Phase 2)
echo -n "sk_live_..." | gcloud secrets versions add STRIPE_SECRET_KEY --data-file=- --project=$PROJECT
```

**2. Enable Firebase Hosting in the console:**

1. Open https://console.firebase.google.com/project/inexxio-dev (replace with your env)
2. Add Firebase to the GCP project if prompted
3. Enable **Hosting** under Build > Hosting
4. Enable **Authentication** under Build > Authentication
   - Enable Email/Link (passwordless) provider
   - Enable Google provider
5. For admin accounts, enable MFA (TOTP) in Authentication settings

**3. Configure GitHub repository:**

Go to your GitHub repository → Settings → Environments and create three environments:
- `development` (no protection rules)
- `staging` (no protection rules)
- `production` (add required reviewers – at least 1 person must approve before prod deploy)

Then add these repository-level variables (Settings → Secrets and variables → Actions → Variables):

```
WORKLOAD_IDENTITY_PROVIDER_DEV=projects/<NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WORKLOAD_IDENTITY_PROVIDER_STAGING=projects/<NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WORKLOAD_IDENTITY_PROVIDER_PROD=projects/<NUMBER>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

The project number is printed by `setup.sh` and available via:
```bash
gcloud projects describe inexxio-dev --format="value(projectNumber)"
```

**4. Connect custom domain (prod only):**

```bash
firebase hosting:sites:create inexxio --project inexxio-prod
firebase target:apply hosting prod inexxio --project inexxio-prod
# Then add inexxio.com DNS records as shown in Firebase Console
```

---

## CI/CD Workflows

### deploy-dev.yml (push to `develop`)

1. Authenticates to GCP via Workload Identity Federation
2. Builds backend Docker image and pushes to Artifact Registry
3. Deploys to Cloud Run `inexxio-backend-dev`
4. Installs frontend dependencies and builds Next.js
5. Deploys to Firebase Hosting project `inexxio-dev`

### deploy-staging.yml (push to `staging`)

Same as dev, targeting the staging GCP project and Firebase project.

### deploy-prod.yml (push to `main`)

1. **Awaits manual approval** via GitHub Environment `production` protection rules
2. After approval: same flow as dev/staging targeting prod resources
3. Cloud Run runs with `--min-instances 1` (always warm) and `--memory 1Gi`

---

## Cloud Run Backend

### Connection to Cloud SQL

The backend connects to PostgreSQL via Unix socket (no public IP, no Cloud SQL Auth Proxy sidecar needed on Cloud Run):

```
/cloudsql/inexxio-{env}:europe-west6:inexxio-{env}-db
```

The `DATABASE_URL` secret uses this format:
```
postgresql+asyncpg://inexxio:PASSWORD@/inexxio?host=/cloudsql/inexxio-dev:europe-west6:inexxio-dev-db
```

### Startup sequence

The backend Dockerfile runs `/app/start.sh` which:
1. Executes `alembic upgrade head` (applies pending DB migrations)
2. Starts `uvicorn app.main:app` on port 8080

This ensures schema is always up-to-date on every deploy.

### Environment-specific resource limits

| Setting          | dev     | staging | prod     |
|------------------|---------|---------|----------|
| Min instances    | 0       | 0       | 1        |
| Max instances    | 3       | 5       | 10       |
| Memory           | 512Mi   | 512Mi   | 1Gi      |
| CPU              | 1       | 1       | 2        |
| Concurrency      | 80      | 80      | 80       |

---

## Firebase Hosting

### Configuration (`firebase.json`)

- Next.js SSR served via Firebase Web Frameworks in europe-west6
- `/api/**` rewrites to the Cloud Run backend service
- Security headers on all responses:
  - `X-Frame-Options: SAMEORIGIN`
  - `X-Content-Type-Options: nosniff`
  - `Strict-Transport-Security` (HSTS, 1 year, preload)
  - `Content-Security-Policy` (restricts scripts/styles/fonts/images/connections)
  - `Permissions-Policy`
- Static assets (JS/CSS/fonts) cached for 1 year (immutable)
- ERP/admin routes marked `noindex, nofollow` with `no-store` cache

### Project aliases (`.firebaserc`)

```json
{
  "projects": {
    "dev":     "inexxio-dev",
    "staging": "inexxio-staging",
    "prod":    "inexxio-prod"
  }
}
```

Deploy manually: `firebase deploy --only hosting --project inexxio-dev`

---

## Docker Images

### Backend (`backend/Dockerfile`)

Multi-stage build:
- **builder**: python:3.12-slim, compiles dependencies
- **runtime**: python:3.12-slim, copies compiled packages, runs as non-root `appuser` (uid 1001)

Port: 8080. Entrypoint: `/app/start.sh` (alembic + uvicorn).

```bash
# Build locally
docker build -t inexxio-backend:local ./backend

# Run locally (requires a running PostgreSQL and env vars)
docker run -p 8080:8080 \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e SECRET_KEY="..." \
  inexxio-backend:local
```

### Frontend (`frontend/Dockerfile`)

Multi-stage build (fallback if Firebase Hosting is unavailable):
- **deps**: node:20-alpine, installs npm dependencies
- **builder**: builds Next.js with `output: 'standalone'`
- **runtime**: node:20-alpine, runs as non-root `nextjs` (uid 1001)

Port: 8080. Entrypoint: `node server.js`.

---

## Secret Manager Reference

| Secret Name          | Description                               | Consumed by      |
|----------------------|-------------------------------------------|------------------|
| `DATABASE_URL`       | PostgreSQL asyncpg connection string      | Cloud Run        |
| `FIREBASE_PROJECT_ID`| Firebase project ID                       | Cloud Run        |
| `SECRET_KEY`         | JWT signing key (hex 32 bytes)            | Cloud Run        |
| `GCS_BUCKET`         | GCS bucket name for file storage          | Cloud Run        |
| `CLAUDE_API_KEY`     | Anthropic Claude API key (Phase 1)        | Cloud Run        |
| `STRIPE_SECRET_KEY`  | Stripe secret key (Phase 2)               | Cloud Run        |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret (Phase 2)| Cloud Run        |

Update a secret:
```bash
echo -n "new-value" | gcloud secrets versions add SECRET_NAME \
  --data-file=- --project=inexxio-dev
```

List secret versions:
```bash
gcloud secrets versions list SECRET_NAME --project=inexxio-dev
```

---

## Monitoring & Logging

- Cloud Run logs: `gcloud run services logs read inexxio-backend-dev --region=europe-west6`
- Cloud SQL logs: Cloud Console → Logging → Cloud SQL
- Uptime checks: Configure in Cloud Monitoring → Uptime Checks → `https://inexxio.web.app/api/v1/health`

---

## Rollback

```bash
# List recent Cloud Run revisions
gcloud run revisions list \
  --service=inexxio-backend-prod \
  --region=europe-west6 \
  --project=inexxio-prod

# Route 100% traffic to a previous revision
gcloud run services update-traffic inexxio-backend-prod \
  --to-revisions=inexxio-backend-prod-XXXXX=100 \
  --region=europe-west6 \
  --project=inexxio-prod
```

For frontend, redeploy a previous Git commit by reverting and pushing to the target branch.
