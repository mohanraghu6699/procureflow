#!/usr/bin/env bash
# Deletes everything deploy.sh created: both Cloud Run services, the Cloud SQL instance (and all its data),
# the secrets, the container images repository and the runtime service account.
#
# Run from anywhere:  bash deploy/gcp/destroy.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

confirm "DELETE the ProcureFlow Cloud Run services, Cloud SQL instance '${SQL_INSTANCE}' (all data), secrets and images"

for service in "$WEB_SERVICE" "$API_SERVICE"; do
  if gcloud run services describe "$service" --region "$REGION" >/dev/null 2>&1; then
    log "Deleting Cloud Run service ${service}"
    gcloud run services delete "$service" --region "$REGION" --quiet
  fi
done

if gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
  log "Deleting Cloud SQL instance ${SQL_INSTANCE}"
  gcloud sql instances delete "$SQL_INSTANCE" --quiet
fi

seed_secrets=()
for role in $SEED_ROLES; do seed_secrets+=("$(seed_secret_name "$role")"); done
for secret in "$SECRET_DATABASE_URL" "$SECRET_DB_PASSWORD" "$SECRET_JWT" "${seed_secrets[@]}"; do
  if gcloud secrets describe "$secret" >/dev/null 2>&1; then
    log "Deleting secret ${secret}"
    gcloud secrets delete "$secret" --quiet
  fi
done

if gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1; then
  log "Deleting Artifact Registry repository ${REPO}"
  gcloud artifacts repositories delete "$REPO" --location "$REGION" --quiet
fi

for sa in "$RUN_SA" "$WEB_SA" "$BUILD_SA"; do
  if gcloud iam service-accounts describe "$sa" >/dev/null 2>&1; then
    log "Deleting service account ${sa}"
    gcloud iam service-accounts delete "$sa" --quiet
  fi
done

cat <<EOF

Done. Left in place on purpose (free, and shared with other work in this project):
  - the enabled Google Cloud APIs
  - the small Cloud Build source-upload bucket (gs://${PROJECT_ID}_cloudbuild)
Note: Google reserves a deleted Cloud SQL instance name for about a week, so re-deploying right away
needs a new name, e.g.  SQL_INSTANCE=${SQL_INSTANCE}-2 bash deploy/gcp/deploy.sh
EOF
