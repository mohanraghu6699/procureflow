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
#   bash deploy/gcp/update.sh --reset-data       # also DELETE all purchase requests, orders, deliveries and history for
#                                                # a clean demo start (accounts and master data stay; asks you to type RESET)
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
RESET=""
for arg in "$@"; do
  case "$arg" in
    all | api | web) TARGET="$arg" ;;
    --sync-passwords) SYNC=1 ;;
    --reset-data) RESET=1 ;;
    *) die "Usage: bash deploy/gcp/update.sh [all|api|web] [--sync-passwords] [--reset-data]" ;;
  esac
done
if [ "$TARGET" = "web" ] && { [ -n "$SYNC" ] || [ -n "$RESET" ]; }; then
  die "--sync-passwords and --reset-data run the API image, so use them with 'all' (the default) or 'api', not 'web'."
fi

require_vars LOG_LEVEL ACCESS_TOKEN_EXPIRE_MINUTES JWT_ALGORITHM   # the API has no built-in defaults

extras=""
[ -z "$SYNC" ] || extras="${extras} and SET the seeded accounts' passwords from ${ENV_FILE##*/}"
[ -z "$RESET" ] || extras="${extras} and CLEAR all purchase requests, orders and deliveries"
confirm "build and deploy new code (${TARGET})${extras}; no infrastructure is created or deleted"
[ -z "$RESET" ] || confirm_reset "This will DELETE every purchase request, purchase order, delivery and status-history entry in project ${PROJECT_ID}. Accounts and master data are kept. It cannot be undone."

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
[ -z "$RESET" ] || run_data_reset

# Idempotent: makes sure the API still trusts the web app's URL.
[ -z "${WEB_URL:-}" ] || allow_cors
smoke_test
[ -z "$SYNC" ] || verify_password_sync
[ -z "$RESET" ] || verify_data_reset
print_summary
