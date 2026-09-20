#!/usr/bin/env bash
# Deploys ProcureFlow to Google Cloud:
#   Cloud SQL (PostgreSQL 16)  <-  Cloud Run "api" (FastAPI)  <-  Cloud Run "web" (React on nginx)
# Images are built remotely with Cloud Build, so Docker is not needed on this machine.
# Safe to re-run: existing resources are reused and both services are redeployed from the current code.
# Remove everything again with deploy/gcp/destroy.sh.
#
# Run from anywhere:  bash deploy/gcp/deploy.sh      (Git Bash on Windows, or Cloud Shell)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.."   # repo root: gcloud gets relative paths, which behave the same on Windows and Linux
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=services.sh
source "$HERE/services.sh"

TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

require_vars LOG_LEVEL ACCESS_TOKEN_EXPIRE_MINUTES JWT_ALGORITHM   # the API has no built-in defaults

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
log "Secrets: database password and JWT signing key"
[ "$DB_USER" = "postgres" ] || die "DB_USER must be 'postgres', Cloud SQL's built-in admin. A dedicated user would need schema grants that this script does not set up."
# Database password: the value from the env file when given, otherwise generated once and reused.
if [ -n "${DB_PASSWORD:-}" ]; then
  [[ "$DB_PASSWORD" =~ ^[A-Za-z0-9._~-]{16,}$ ]] \
    || die "DB_PASSWORD must be at least 16 characters, using only letters, digits and . _ ~ - (it is embedded in the database connection URL)."
  put_secret "$SECRET_DB_PASSWORD" "$DB_PASSWORD"
elif ! secret_exists "$SECRET_DB_PASSWORD"; then
  openssl rand -hex 24 | tr -d '\n' | gcloud secrets create "$SECRET_DB_PASSWORD" --replication-policy=automatic --data-file=-
fi
# JWT signing key: the value from the env file when given, otherwise generated once and reused.
if [ -n "${JWT_SECRET_KEY:-}" ]; then
  [ "${#JWT_SECRET_KEY}" -ge 32 ] || die "JWT_SECRET_KEY in the deploy env file must be at least 32 characters."
  put_secret "$SECRET_JWT" "$JWT_SECRET_KEY"
elif ! secret_exists "$SECRET_JWT"; then
  openssl rand -hex 32 | tr -d '\n' | gcloud secrets create "$SECRET_JWT" --replication-policy=automatic --data-file=-
fi
DB_PASSWORD="$(secret_value "$SECRET_DB_PASSWORD")"

# Login passwords for the seeded accounts, from SEED_<ROLE>_PASSWORD in the env file. The API only uses them
# when it seeds an empty database; a role left empty gets a random password that the seed prints to the log.
log "Login passwords for the seeded accounts (only applied when the database is first created)"
for role in $SEED_ROLES; do
  var="SEED_${role}_PASSWORD"
  value="${!var:-}"
  if [ -n "$value" ]; then
    [ "${#value}" -ge 8 ] || die "${var} must be at least 8 characters."
    put_secret "$(seed_secret_name "$role")" "$value"
  fi
done

# ---------------------------------------------------------------------------------------------
new_instance=""
if ! gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
  log "Creating Cloud SQL instance ${SQL_INSTANCE} (${SQL_TIER}) — this takes 5-10 minutes"
  gcloud sql instances create "$SQL_INSTANCE" \
    --database-version=POSTGRES_16 --edition=ENTERPRISE --tier="$SQL_TIER" \
    --region="$REGION" --availability-type=zonal --storage-size=10 --no-backup
  new_instance=1
else
  log "Cloud SQL instance ${SQL_INSTANCE} already exists — reusing it"
fi
CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"

log "Database"
if ! gcloud sql databases describe "$DB_NAME" --instance "$SQL_INSTANCE" >/dev/null 2>&1; then
  gcloud sql databases create "$DB_NAME" --instance "$SQL_INSTANCE"
fi
# The app connects as the built-in 'postgres' user so it owns the schema it migrates. A dedicated
# least-privilege user is a sensible hardening step for a real deployment (see README).
DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
# The secret has to exist before its permissions are set below. Bringing its value (and the database user's
# password) up to date happens later, right before the API is released.
secret_exists "$SECRET_DATABASE_URL" || put_secret "$SECRET_DATABASE_URL" "$DATABASE_URL"

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
runtime_secrets=("$SECRET_DATABASE_URL" "$SECRET_JWT")
for role in $SEED_ROLES; do
  secret_exists "$(seed_secret_name "$role")" && runtime_secrets+=("$(seed_secret_name "$role")")
done
for secret in "${runtime_secrets[@]}"; do
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
build_api

# Database credentials: applied after the (slow) build and immediately before the release, so a failed build
# changes nothing and the running API is without valid credentials only for the seconds until the new revision
# starts. Only when they actually changed: a new instance, or a different DB_USER/password than the stored URL.
if [ -n "$new_instance" ] || [ "$(secret_value "$SECRET_DATABASE_URL")" != "$DATABASE_URL" ]; then
  log "Applying the database credentials (user ${DB_USER}) to Cloud SQL and Secret Manager"
  gcloud sql users set-password "$DB_USER" --instance "$SQL_INSTANCE" --password "$DB_PASSWORD"
  put_secret "$SECRET_DATABASE_URL" "$DATABASE_URL"
else
  log "Database credentials unchanged"
fi

release_api
deploy_web
allow_cors
smoke_test
show_generated_passwords
print_summary
