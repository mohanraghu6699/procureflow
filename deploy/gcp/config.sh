#!/usr/bin/env bash
# Settings and helpers shared by deploy.sh and destroy.sh (sourced, not run directly).
# Override any value from the environment, e.g.:
#   PROJECT_ID=my-project REGION=europe-west1 bash deploy/gcp/deploy.sh

# Note: do NOT set MSYS_NO_PATHCONV here. Git Bash's automatic path conversion is what lets gcloud's launcher
# hand /c/... paths to the Windows Python; disabling it breaks every gcloud call. No argument below needs it
# (the one value starting with "/", the database URL's socket path, travels over stdin, not as an argument).

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# On Windows, plain "bash" in PowerShell/cmd is usually WSL, which has none of these. Say so instead of failing oddly later.
for tool in gcloud openssl curl; do
  command -v "$tool" >/dev/null 2>&1 \
    || die "'${tool}' not found in this shell. On Windows run this from Git Bash (not WSL/PowerShell), or use Cloud Shell."
done

# gcloud's Unix launcher looks for "python" on PATH; on Windows that can hit the broken Microsoft Store
# stub ("Python was not found..."). Use the interpreter bundled with the SDK instead when there is one.
if [ -z "${CLOUDSDK_PYTHON:-}" ]; then
  _sdk_root="$(dirname "$(dirname "$(command -v gcloud)")")"
  if [ -x "${_sdk_root}/platform/bundledpython/python.exe" ]; then
    export CLOUDSDK_PYTHON="${_sdk_root}/platform/bundledpython/python.exe"
  fi
fi

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
APP="${APP:-procureflow}"

SQL_INSTANCE="${SQL_INSTANCE:-${APP}-db}"
SQL_TIER="${SQL_TIER:-db-f1-micro}"   # smallest shared-core instance
DB_NAME="${DB_NAME:-procureflow}"

API_SERVICE="${APP}-api"
WEB_SERVICE="${APP}-web"
REPO="${APP}"                          # Artifact Registry repository for the images
RUN_SA_NAME="${APP}-run"               # service account the API runs as
WEB_SA_NAME="${APP}-web"               # identity of the web (nginx) service; it needs no permissions at all
BUILD_SA_NAME="${APP}-build"           # service account Cloud Build runs image builds as
SECRET_DB_PASSWORD="${APP}-db-password"
SECRET_DATABASE_URL="${APP}-database-url"
SECRET_JWT="${APP}-jwt-secret"

log() { printf '\n==> %s\n' "$*"; }

[ -n "$PROJECT_ID" ] || die "No project set. Run 'gcloud config set project <id>' or pass PROJECT_ID=<id>."

# Every gcloud call in the scripts targets this project without changing the user's saved gcloud config.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

RUN_SA="${RUN_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WEB_SA="${WEB_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Shows where we are about to act and asks for a yes. Skip with ASSUME_YES=1.
confirm() {
  local action="$1"
  echo "Account : $(gcloud config get-value account 2>/dev/null)"
  echo "Project : ${PROJECT_ID}"
  echo "Region  : ${REGION}"
  echo "Action  : ${action}"
  [ "${ASSUME_YES:-}" = "1" ] && return 0
  read -r -p "Continue? [y/N] " answer
  case "$answer" in y | Y | yes | YES) ;; *) echo "Cancelled."; exit 1 ;; esac
}

# retry <attempts> <delay-seconds> <command...> — newly created IAM objects can take a few seconds to be visible.
retry() {
  local attempts="$1" delay="$2" n=1
  shift 2
  until "$@"; do
    [ "$n" -ge "$attempts" ] && return 1
    n=$((n + 1))
    sleep "$delay"
  done
}
