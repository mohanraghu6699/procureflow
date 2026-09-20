#!/usr/bin/env bash
# Build-and-deploy steps shared by deploy.sh (first-time setup) and update.sh (code-only redeploy).
# Sourced after config.sh. The caller must set: TAG, IMAGE_BASE, BUILD_SA_PATH, CONNECTION_NAME, PROJECT_NUMBER.

service_url() { gcloud run services describe "$1" --region "$REGION" --format='value(status.url)'; }

# Browser origins the API must accept: the web app's addresses plus CORS_EXTRA_ORIGINS from the env file.
# Cloud Run serves a service on two address forms. The predictable one (SERVICE-PROJECTNUMBER.REGION.run.app)
# is known before the web app exists, so the API starts with a valid value on a first deploy; the other form is
# added as soon as the web service exists (and again by allow_cors after it is deployed).
cors_origins() {
  local predictable="https://${WEB_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app" origins web_url
  origins="$predictable"
  web_url="$(service_url "$WEB_SERVICE" 2>/dev/null || true)"
  if [ -n "$web_url" ] && [ "$web_url" != "$predictable" ]; then origins="${web_url},${origins}"; fi
  if [ -n "${CORS_EXTRA_ORIGINS:-}" ]; then origins="${origins},${CORS_EXTRA_ORIGINS}"; fi
  printf '%s' "$origins"
}

# Every setting the API reads, as environment variables. None has a default in the application, so all of
# them are always passed: LOG_LEVEL, ACCESS_TOKEN_EXPIRE_MINUTES and JWT_ALGORITHM come from the env file /
# shell (deploy.sh and update.sh check they are set), CORS_ORIGINS is computed. "@" separates the entries
# because gcloud's default separator, ",", appears inside CORS_ORIGINS.
api_plain_env() {
  printf 'LOG_LEVEL=%s@ACCESS_TOKEN_EXPIRE_MINUTES=%s@JWT_ALGORITHM=%s@CORS_ORIGINS=%s' \
    "$LOG_LEVEL" "$ACCESS_TOKEN_EXPIRE_MINUTES" "$JWT_ALGORITHM" "$(cors_origins)"
}

# Secret Manager values handed to the API as environment variables. The seed passwords are included only for
# roles that have one (see SEED_<ROLE>_PASSWORD in the env file).
api_secret_mappings() {
  local out="DATABASE_URL=${SECRET_DATABASE_URL}:latest,JWT_SECRET_KEY=${SECRET_JWT}:latest" role name
  for role in $SEED_ROLES; do
    name="$(seed_secret_name "$role")"
    if secret_exists "$name"; then out="${out},SEED_${role}_PASSWORD=${name}:latest"; fi
  done
  printf '%s' "$out"
}

# Builds the API image and rolls out a new revision. Database migrations run as the container starts
# (alembic upgrade head, then seeding if the database is empty, then the server): if a migration fails the
# new revision never becomes ready and Cloud Run keeps serving the previous one.
deploy_api() {
  build_api
  release_api
}

build_api() {
  log "Building the API image"
  gcloud builds submit backend --config deploy/gcp/cloudbuild-api.yaml \
    --substitutions "_IMAGE=${IMAGE_BASE}/api:${TAG}" --service-account "$BUILD_SA_PATH" --quiet
}

# Rolls out the image built by build_api. Split from it so deploy.sh can change the database credentials in
# between: after the slow build, right before the release, keeping the running API without valid credentials
# for seconds instead of minutes (and never changing them at all if the build fails).
release_api() {
  log "Releasing the API (database migrations run when the new revision starts)"
  gcloud run deploy "$API_SERVICE" \
    --image "${IMAGE_BASE}/api:${TAG}" --region "$REGION" \
    --port 8000 --allow-unauthenticated \
    --service-account "$RUN_SA" \
    --add-cloudsql-instances "$CONNECTION_NAME" \
    --set-secrets "$(api_secret_mappings)" \
    --update-env-vars "^@^$(api_plain_env)" \
    --cpu-boost --min-instances "$API_MIN_INSTANCES" --max-instances 1 --memory 512Mi --quiet
  API_URL="$(service_url "$API_SERVICE")"
}

# ---- --sync-passwords (update.sh) -------------------------------------------------------------------
# The seed only creates accounts in an EMPTY database, so passwords in the env file never reach accounts that
# already exist. This makes them do so on request: the values go to Secret Manager, then a one-off Cloud Run job
# runs the API image's "python -m app.seed --sync-passwords" against the live database, then the job is removed.

# Step 1 (before the API is released): store the SEED_<ROLE>_PASSWORD values and let the API's identity read them.
prepare_password_sync() {
  local role var value name any=""
  log "Storing the seed passwords from the env file in Secret Manager"
  for role in $SEED_ROLES; do
    var="SEED_${role}_PASSWORD"
    value="${!var:-}"
    [ -n "$value" ] || continue
    [ "${#value}" -ge 8 ] || die "${var} must be at least 8 characters."
    name="$(seed_secret_name "$role")"
    put_secret "$name" "$value"
    retry 6 10 gcloud secrets add-iam-policy-binding "$name" \
      --member "serviceAccount:${RUN_SA}" --role roles/secretmanager.secretAccessor --quiet >/dev/null
    any=1
  done
  [ -n "$any" ] || die "--sync-passwords needs at least one of SEED_ADMIN_PASSWORD, SEED_REQUESTER_PASSWORD, SEED_APPROVER_PASSWORD in the deploy env file."
}

# Step 2 (after the release, so the image is the one that contains --sync-passwords): the one-off job.
run_password_sync() {
  local job="${APP}-sync-passwords" rc=0
  log "Applying the seed passwords to the existing accounts (one-off Cloud Run job, removed afterwards)"
  gcloud run jobs deploy "$job" \
    --image "${IMAGE_BASE}/api:${TAG}" --region "$REGION" \
    --service-account "$RUN_SA" \
    --set-cloudsql-instances "$CONNECTION_NAME" \
    --set-secrets "$(api_secret_mappings)" \
    --set-env-vars "^@^$(api_plain_env)" \
    --command python --args "^@^-m@app.seed@--sync-passwords" \
    --max-retries 0 --task-timeout 300 --quiet
  gcloud run jobs execute "$job" --region "$REGION" --wait --quiet || rc=$?
  gcloud run jobs delete "$job" --region "$REGION" --quiet || true
  [ "$rc" = "0" ] || die "The password sync failed (the job is already removed; re-run to retry). Its log: gcloud logging read 'resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${job}\"' --limit 30 --freshness 1h"
}

# Step 3: prove it worked, by logging in as one account per role with the password from the env file.
verify_password_sync() {
  local role var value email code body
  log "Checking the new passwords"
  for role in $SEED_ROLES; do
    var="SEED_${role}_PASSWORD"
    value="${!var:-}"
    [ -n "$value" ] || continue
    case "$role" in
      ADMIN) email="admin@procureflow.com" ;;
      REQUESTER) email="rohan.sharma@procureflow.com" ;;
      APPROVER) email="sameer.khan@procureflow.com" ;;
    esac
    value="${value//\\/\\\\}"; value="${value//\"/\\\"}"   # escape for the JSON body
    body="{\"email\":\"${email}\",\"password\":\"${value}\"}"
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API_URL}/api/auth/login" -H "Content-Type: application/json" -d "$body")"
    [ "$code" = "200" ] || die "After the sync, ${email} could not log in with ${var} (HTTP ${code})."
    echo "  ${email} logs in with ${var}: OK"
  done
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
  local origins
  origins="$(cors_origins)"
  log "Allowing ${origins} to call the API (CORS)"
  gcloud run services update "$API_SERVICE" --region "$REGION" \
    --update-env-vars "^@^CORS_ORIGINS=${origins}" --quiet
}

smoke_test() {
  log "Smoke test"
  local ok=0
  for _ in $(seq 1 20); do
    if curl -sf "${API_URL}/api/health" >/dev/null; then ok=1; break; fi
    sleep 3
  done
  [ "$ok" = "1" ] || die "API did not become healthy. Check logs: gcloud run services logs read ${API_SERVICE} --region ${REGION}"
  # A wrong password must be answered with 401. That proves the API reached the database (so the migrations
  # ran) without this script needing any credentials.
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API_URL}/api/auth/login" \
    -H "Content-Type: application/json" -d '{"email":"nobody@example.com","password":"not-a-real-password"}')"
  [ "$code" = "401" ] || die "The API is up but login answered HTTP ${code} instead of 401 (database problem?). Logs: gcloud run services logs read ${API_SERVICE} --region ${REGION}"
  if [ -n "${WEB_URL:-}" ]; then
    curl -sf "${WEB_URL}/" | grep -q 'id="root"' || die "The web app is not serving"
  fi
}

# On a first deploy the seed script generates the login passwords and prints them to the API log.
# Show them here once (best effort: the log can lag a few seconds behind).
show_generated_passwords() {
  local lines=""
  for _ in 1 2 3; do
    lines="$(gcloud run services logs read "$API_SERVICE" --region "$REGION" --limit 300 2>/dev/null \
      | grep -E "Generated .* password|password: taken from" || true)"
    [ -n "$lines" ] && break
    sleep 5
  done
  if [ -n "$lines" ]; then
    log "Login passwords created by this deploy (note them now)"
    echo "$lines"
  fi
}

print_summary() {
  cat <<EOF

Deployed.
  Web app : ${WEB_URL:-"(not deployed)"}
  API     : ${API_URL}   (Swagger UI: ${API_URL}/docs)
  Logins  : the seeded emails are in the README. No password is stored in the repo: a first deploy
            generates them (shown above); change them later with "Change Password" in the profile menu.

This is a public URL with only synthetic data. Cloud SQL is billed for as long as it exists, so remove
everything when you are done:  bash deploy/gcp/destroy.sh
EOF
}
