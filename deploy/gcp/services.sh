#!/usr/bin/env bash
# Build-and-deploy steps shared by deploy.sh (first-time setup) and update.sh (code-only redeploy).
# Sourced after config.sh. The caller must set: TAG, IMAGE_BASE, BUILD_SA_PATH, CONNECTION_NAME, PROJECT_NUMBER.

service_url() { gcloud run services describe "$1" --region "$REGION" --format='value(status.url)'; }

# Builds the API image and rolls out a new revision. Database migrations run as the container starts
# (alembic upgrade head, then seeding if the database is empty, then the server): if a migration fails the
# new revision never becomes ready and Cloud Run keeps serving the previous one.
deploy_api() {
  log "Building and deploying the API (database migrations run when the new revision starts)"
  gcloud builds submit backend --config deploy/gcp/cloudbuild-api.yaml \
    --substitutions "_IMAGE=${IMAGE_BASE}/api:${TAG}" --service-account "$BUILD_SA_PATH" --quiet
  # --update-env-vars (not --set-env-vars) so settings added elsewhere, notably CORS_ORIGINS, survive a redeploy.
  gcloud run deploy "$API_SERVICE" \
    --image "${IMAGE_BASE}/api:${TAG}" --region "$REGION" \
    --port 8000 --allow-unauthenticated \
    --service-account "$RUN_SA" \
    --add-cloudsql-instances "$CONNECTION_NAME" \
    --set-secrets "DATABASE_URL=${SECRET_DATABASE_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT}:latest" \
    --update-env-vars "LOG_LEVEL=INFO" \
    --min-instances 0 --max-instances 1 --memory 512Mi --quiet
  API_URL="$(service_url "$API_SERVICE")"
}

# Builds the web image and rolls out a new revision. Needs API_URL: it is baked into the JavaScript bundle.
deploy_web() {
  log "Building and deploying the web app (API URL ${API_URL} is baked into the bundle)"
  gcloud builds submit frontend --config deploy/gcp/cloudbuild-web.yaml \
    --substitutions "_IMAGE=${IMAGE_BASE}/web:${TAG},_API_URL=${API_URL}" --service-account "$BUILD_SA_PATH" --quiet
  gcloud run deploy "$WEB_SERVICE" \
    --image "${IMAGE_BASE}/web:${TAG}" --region "$REGION" \
    --port 80 --allow-unauthenticated \
    --service-account "$WEB_SA" \
    --min-instances 0 --max-instances 2 --memory 256Mi --quiet
  WEB_URL="$(service_url "$WEB_SERVICE")"
}

# The API only accepts browser calls from the web app's origin. Cloud Run serves a service on two URL
# forms, so allow both. (The "^@^" prefix makes "@" the list separator so the commas in the value survive.)
allow_cors() {
  local alt_web_url="https://${WEB_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app"
  log "Allowing ${WEB_URL} to call the API (CORS)"
  gcloud run services update "$API_SERVICE" --region "$REGION" \
    --update-env-vars "^@^CORS_ORIGINS=${WEB_URL},${alt_web_url}" --quiet
}

smoke_test() {
  log "Smoke test"
  local ok=0
  for _ in $(seq 1 20); do
    if curl -sf "${API_URL}/api/health" >/dev/null; then ok=1; break; fi
    sleep 3
  done
  [ "$ok" = "1" ] || die "API did not become healthy. Check logs: gcloud run services logs read ${API_SERVICE} --region ${REGION}"
  curl -sf -X POST "${API_URL}/api/auth/login" -H "Content-Type: application/json" \
    -d '{"email":"admin@procureflow.com","password":"Admin@123"}' | grep -q access_token \
    || die "Login with the seeded admin failed"
  if [ -n "${WEB_URL:-}" ]; then
    curl -sf "${WEB_URL}/" | grep -q 'id="root"' || die "The web app is not serving"
  fi
}

print_summary() {
  cat <<EOF

Deployed.
  Web app : ${WEB_URL:-"(not deployed)"}
  API     : ${API_URL}   (Swagger UI: ${API_URL}/docs)
  Login   : admin@procureflow.com / Admin@123   (other demo accounts are in the README)

This is a public URL with well-known demo passwords and only synthetic data. Cloud SQL is billed for as
long as it exists, so remove everything when you are done:  bash deploy/gcp/destroy.sh
EOF
}
