#!/usr/bin/env bash
# Ships new code to an EXISTING deployment: rebuilds and redeploys the API and/or the web app.
# Nothing else is touched: Cloud SQL, secrets, service accounts and permissions stay exactly as they are and the
# database keeps its data (the one exception is --sync-passwords, below). Use deploy.sh once to create the
# infrastructure, then this for every code change.
#
#   bash deploy/gcp/update.sh          # API + web (default)
#   bash deploy/gcp/update.sh api      # backend only (includes its database migrations)
#   bash deploy/gcp/update.sh web      # frontend only
#   bash deploy/gcp/update.sh --sync-passwords   # also apply the SEED_*_PASSWORD values from deploy/gcp/.env to the
#                                                # existing seeded accounts (combine with api or all; not with web)
#
# Database migrations run automatically when the new API revision starts. If one fails, the revision never
# becomes ready and Cloud Run keeps serving the previous version, so a bad migration does not take the app down.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.."   # repo root: gcloud gets relative paths, which behave the same on Windows and Linux
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=services.sh
source "$HERE/services.sh"

TARGET="all"
SYNC=""
for arg in "$@"; do
  case "$arg" in
    all | api | web) TARGET="$arg" ;;
    --sync-passwords) SYNC=1 ;;
    *) die "Usage: bash deploy/gcp/update.sh [all|api|web] [--sync-passwords]" ;;
  esac
done
[ -z "$SYNC" ] || [ "$TARGET" != "web" ] || die "--sync-passwords runs the API image, so use it with 'all' (the default) or 'api', not 'web'."

require_vars LOG_LEVEL ACCESS_TOKEN_EXPIRE_MINUTES JWT_ALGORITHM   # the API has no built-in defaults

if [ -n "$SYNC" ]; then
  confirm "build and deploy new code (${TARGET}) and SET the seeded accounts' passwords from ${ENV_FILE##*/}; no infrastructure is created or deleted"
else
  confirm "build and deploy new code (${TARGET}); no infrastructure is created or deleted"
fi

# Fail early, with a pointer to deploy.sh, if the infrastructure this relies on is not there.
missing=0
need() {
  local what="$1"
  shift
  if ! "$@" >/dev/null 2>&1; then
    echo "Missing: ${what}"
    missing=1
  fi
}
need "Cloud SQL instance ${SQL_INSTANCE}" gcloud sql instances describe "$SQL_INSTANCE"
need "secret ${SECRET_DATABASE_URL}" gcloud secrets describe "$SECRET_DATABASE_URL"
need "secret ${SECRET_JWT}" gcloud secrets describe "$SECRET_JWT"
need "service account ${RUN_SA}" gcloud iam service-accounts describe "$RUN_SA"
need "service account ${WEB_SA}" gcloud iam service-accounts describe "$WEB_SA"
need "service account ${BUILD_SA}" gcloud iam service-accounts describe "$BUILD_SA"
need "Artifact Registry repository ${REPO}" gcloud artifacts repositories describe "$REPO" --location "$REGION"
if [ "$TARGET" = "web" ]; then
  need "Cloud Run service ${API_SERVICE} (the web app needs its URL)" \
    gcloud run services describe "$API_SERVICE" --region "$REGION"
fi
[ "$missing" = "0" ] || die "The deployment does not exist yet (or is incomplete). Run 'bash deploy/gcp/deploy.sh' first."

TAG="${TAG:-$(date +%Y%m%d%H%M%S)}"
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CONNECTION_NAME="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(connectionName)')"
BUILD_SA_PATH="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA}"

[ -z "$SYNC" ] || prepare_password_sync

case "$TARGET" in
  api)
    deploy_api
    WEB_URL="$(service_url "$WEB_SERVICE" 2>/dev/null || true)"   # for the CORS re-check and the smoke test
    ;;
  web)
    API_URL="$(service_url "$API_SERVICE")"
    deploy_web
    ;;
  all)
    deploy_api
    deploy_web
    ;;
esac

[ -z "$SYNC" ] || run_password_sync

# Idempotent: makes sure the API still trusts the web app's URL.
[ -z "${WEB_URL:-}" ] || allow_cors
smoke_test
[ -z "$SYNC" ] || verify_password_sync
print_summary
