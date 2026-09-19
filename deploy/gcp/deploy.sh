#!/usr/bin/env bash
# Deploys ProcureFlow to Google Cloud:
#   Cloud SQL (PostgreSQL 16)  <-  Cloud Run "api" (FastAPI)  <-  Cloud Run "web" (React on nginx)
# Images are built remotely with Cloud Build, so Docker is not needed on this machine.
# Safe to re-run: existing resources are reused and both services are redeployed from the current code.
# Remove everything again with deploy/gcp/destroy.sh.
#
# Run from anywhere:  bash deploy/gcp/deploy.sh      (Git Bash, WSL or Cloud Shell)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.."   # repo root: gcloud gets relative paths, which behave the same on Windows and Linux
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=services.sh
source "$HERE/services.sh"

TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

confirm "create/update Cloud SQL (billed while it exists), Cloud Run services, secrets and images"

# ---------------------------------------------------------------------------------------------
log "Enabling the Google Cloud APIs this needs (first run takes a minute or two)"
# sql-component is separate from sqladmin: "gcloud run deploy --add-cloudsql-instances" checks for it and,
# with prompts disabled, aborts instead of asking to enable it.
gcloud services enable \
  run.googleapis.com sqladmin.googleapis.com sql-component.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com iam.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

# ---------------------------------------------------------------------------------------------
log "Secrets: database password and JWT signing key (generated once, then reused)"
secret_exists() { gcloud secrets describe "$1" >/dev/null 2>&1; }

if ! secret_exists "$SECRET_DB_PASSWORD"; then
  openssl rand -hex 24 | tr -d '\n' | gcloud secrets create "$SECRET_DB_PASSWORD" --replication-policy=automatic --data-file=-
fi
if ! secret_exists "$SECRET_JWT"; then
  openssl rand -hex 32 | tr -d '\n' | gcloud secrets create "$SECRET_JWT" --replication-policy=automatic --data-file=-
fi
DB_PASSWORD="$(gcloud secrets versions access latest --secret="$SECRET_DB_PASSWORD")"

# ---------------------------------------------------------------------------------------------
if ! gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
  log "Creating Cloud SQL instance ${SQL_INSTANCE} (${SQL_TIER}) — this takes 5-10 minutes"
  gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_16 --edition=ENTERPRISE --tier="$SQL_TIER" \
    --region="$REGION" --availability-type=zonal --storage-size=10 --no-backup
else
  log "Cloud SQL instance ${SQL_INSTANCE} already exists — reusing it"
fi
CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"

log "Database and credentials"
if ! gcloud sql databases describe "$DB_NAME" --instance "$SQL_INSTANCE" >/dev/null 2>&1; then
  gcloud sql databases create "$DB_NAME" --instance "$SQL_INSTANCE"
fi
# The app connects as the built-in 'postgres' user so it owns the schema it migrates. A dedicated
# least-privilege user is a sensible hardening step for a real deployment (see README).
gcloud sql users set-password postgres --instance "$SQL_INSTANCE" --password "$DB_PASSWORD"

DATABASE_URL="postgresql+psycopg2://postgres:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
if ! secret_exists "$SECRET_DATABASE_URL"; then
  printf '%s' "$DATABASE_URL" | gcloud secrets create "$SECRET_DATABASE_URL" --replication-policy=automatic --data-file=-
elif [ "$(gcloud secrets versions access latest --secret="$SECRET_DATABASE_URL")" != "$DATABASE_URL" ]; then
  printf '%s' "$DATABASE_URL" | gcloud secrets versions add "$SECRET_DATABASE_URL" --data-file=-
fi

# ---------------------------------------------------------------------------------------------
log "Service account and permissions"
if ! gcloud iam service-accounts describe "$RUN_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$RUN_SA_NAME" --display-name "ProcureFlow Cloud Run runtime"
fi
# Every Cloud Run service is given an explicit identity: without one Cloud Run falls back to the default
# Compute Engine service account, which this project does not have.
if ! gcloud iam service-accounts describe "$WEB_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$WEB_SA_NAME" --display-name "ProcureFlow web (no permissions)"
fi
retry 6 10 gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${RUN_SA}" --role roles/cloudsql.client --condition=None --quiet >/dev/null
for secret in "$SECRET_DATABASE_URL" "$SECRET_JWT"; do
  retry 6 10 gcloud secrets add-iam-policy-binding "$secret" \
    --member "serviceAccount:${RUN_SA}" --role roles/secretmanager.secretAccessor --quiet >/dev/null
done
# Cloud Build gets its own service account. The default Compute Engine one may not exist (it is only created
# when the Compute Engine API is first enabled) or may lack rights, so nothing here depends on it.
new_build_sa=""
if ! gcloud iam service-accounts describe "$BUILD_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$BUILD_SA_NAME" --display-name "ProcureFlow Cloud Build"
  new_build_sa=1
fi
retry 6 10 gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${BUILD_SA}" --role roles/cloudbuild.builds.builder --condition=None --quiet >/dev/null
if [ -n "$new_build_sa" ]; then
  echo "Waiting for the new permissions to propagate..."
  sleep 20
fi
BUILD_SA_PATH="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA}"

# ---------------------------------------------------------------------------------------------
log "Artifact Registry repository for the images"
if ! gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION" \
    --description "ProcureFlow container images"
fi

# ---------------------------------------------------------------------------------------------
deploy_api
deploy_web
allow_cors
smoke_test
print_summary
