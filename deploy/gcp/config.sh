#!/usr/bin/env bash
# Settings and helpers shared by deploy.sh, update.sh and destroy.sh (sourced, not run directly).
# Values come from deploy/gcp/.env (see .env.example); a variable set in the shell overrides the file, e.g.:
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

# Deployment settings can live in an env file (default: deploy/gcp/.env, git-ignored; see .env.example).
# Precedence: a variable already set in the shell  >  the file  >  the defaults below.
# Format: one KEY=VALUE per line, "#" comment lines, optional "export " prefix and surrounding quotes.
# Do not put a trailing comment after a value.
_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DEPLOY_ENV_FILE:-${_CONFIG_DIR}/.env}"

load_env_file() {
  local file="$1" line key value
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"                 # files saved on Windows end their lines with \r\n
    line="${line#export }"
    case "$line" in '' | '#'*) continue ;; esac
    key="${line%%=*}"
    value="${line#*=}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "$value" in
      \"*\") value="${value#\"}"; value="${value%\"}" ;;
      \'*\') value="${value#\'}"; value="${value%\'}" ;;
    esac
    if [ -z "${!key+x}" ]; then export "$key=$value"; fi   # never override the shell
  done < "$file"
}
load_env_file "$ENV_FILE"

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
APP="${APP:-procureflow}"

SQL_INSTANCE="${SQL_INSTANCE:-${APP}-db}"
SQL_TIER="${SQL_TIER:-db-f1-micro}"   # smallest shared-core instance
DB_NAME="${DB_NAME:-procureflow}"
DB_USER="${DB_USER:-postgres}"        # Cloud SQL's built-in admin; deploy.sh accepts only this for now
# 0 = scale to zero when idle (free, but the first request afterwards waits ~10-15s for a cold start).
# 1 = keep one instance warm (about $10/month). e.g.  API_MIN_INSTANCES=1 bash deploy/gcp/update.sh api
API_MIN_INSTANCES="${API_MIN_INSTANCES:-0}"

API_SERVICE="${APP}-api"
WEB_SERVICE="${APP}-web"
REPO="${APP}"                          # Artifact Registry repository for the images
RUN_SA_NAME="${APP}-run"               # service account the API runs as
WEB_SA_NAME="${APP}-web"               # identity of the web (nginx) service; it needs no permissions at all
BUILD_SA_NAME="${APP}-build"           # service account Cloud Build runs image builds as
SECRET_DB_PASSWORD="${APP}-db-password"
SECRET_DATABASE_URL="${APP}-database-url"
SECRET_JWT="${APP}-jwt-secret"
# The seeded accounts' login passwords (SEED_<ROLE>_PASSWORD in the env file), one secret per role.
SEED_ROLES="ADMIN REQUESTER APPROVER"
seed_secret_name() { printf '%s-seed-%s-password' "$APP" "$(printf '%s' "$1" | tr 'A-Z' 'a-z')"; }

log() { printf '\n==> %s\n' "$*"; }

secret_exists() { gcloud secrets describe "$1" >/dev/null 2>&1; }

# secret_value <name>: the secret's latest value. On Windows gcloud ends its output with \r\n; command substitution
# drops the \n but leaves a lone \r, which would silently become part of the value, so it is removed here.
secret_value() {
  local value
  value="$(gcloud secrets versions access latest --secret="$1")"
  printf '%s' "${value%$'\r'}"
}

# put_secret <name> <value>: create the secret, or add a new version when the stored value differs.
put_secret() {
  local name="$1" value="$2"
  if ! secret_exists "$name"; then
    printf '%s' "$value" | gcloud secrets create "$name" --replication-policy=automatic --data-file=-
  elif [ "$(secret_value "$name")" != "$value" ]; then
    printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=-
  fi
}

[ -n "$PROJECT_ID" ] || die "No project set. Run 'gcloud config set project <id>' or pass PROJECT_ID=<id>."

# Every gcloud call in the scripts targets this project without changing the user's saved gcloud config.
export CLOUDSDK_CORE_PROJECT="$PROJECT_ID"
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

RUN_SA="${RUN_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
WEB_SA="${WEB_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# require_vars <NAME>...: stop, naming every one that is empty or unset. The API has no built-in defaults,
# so the values it needs must come from the deploy env file (or the shell).
require_vars() {
  local missing="" name
  for name in "$@"; do
    [ -n "${!name:-}" ] || missing="${missing} ${name}"
  done
  [ -z "$missing" ] || die "Not set:${missing}. Add them to deploy/gcp/.env (copy deploy/gcp/.env.example) or export them."
}

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

# confirm_reset <what will be deleted>: a destructive action needs the word RESET typed (or CONFIRM_RESET=RESET for a script).
confirm_reset() {
  [ "${CONFIRM_RESET:-}" = "RESET" ] && return 0
  echo "$1"
  read -r -p "Type RESET to continue: " answer
  [ "$answer" = "RESET" ] || { echo "Cancelled."; exit 1; }
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
