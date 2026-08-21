#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="main"
REMOTE_HOST="${EDGE2_REMOTE_HOST:-tony@100.95.242.17}"
REMOTE_DIR="${EDGE2_REMOTE_DIR:-/home/tony/edge2}"
SSH_KEY="${EDGE2_SSH_KEY:-${HOME}/.ssh/edge_server}"
REMOTE_APP_HEALTH_URL="http://127.0.0.1:${EDGE2_APP_PORT:-8792}/health"
REMOTE_INGRESS_HEALTH_URL="http://127.0.0.1:${EDGE2_INGRESS_PORT:-8793}/health"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

for command_name in git make ssh awk; do
  command -v "${command_name}" >/dev/null 2>&1 || fail "Required command not found: ${command_name}"
done

[[ -r "${SSH_KEY}" ]] || fail "SSH key is not readable: ${SSH_KEY}"
[[ "$(git -C "${ROOT_DIR}" branch --show-current)" == "${BRANCH}" ]] || \
  fail "Deployment requires local branch ${BRANCH}"
[[ -z "$(git -C "${ROOT_DIR}" status --porcelain)" ]] || \
  fail "Deployment requires a clean local working tree"
git -C "${ROOT_DIR}" remote get-url origin >/dev/null 2>&1 || \
  fail "Git remote origin is not configured"

printf 'Running the pre-deploy test suite...\n'
make -C "${ROOT_DIR}" test

expected_sha="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
printf 'Pushing %s to origin...\n' "${BRANCH}"
git -C "${ROOT_DIR}" push origin "${BRANCH}"
origin_sha="$(git -C "${ROOT_DIR}" ls-remote --exit-code origin "refs/heads/${BRANCH}" | awk 'NR == 1 {print $1}')"
[[ "${origin_sha}" == "${expected_sha}" ]] || \
  fail "origin/${BRANCH} does not match local HEAD after push"

ssh_options=(-i "${SSH_KEY}" -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes)
if ! remote_output="$(
  ssh "${ssh_options[@]}" "${REMOTE_HOST}" bash -s -- \
    "${REMOTE_DIR}" "${BRANCH}" "${expected_sha}" \
    "${REMOTE_APP_HEALTH_URL}" "${REMOTE_INGRESS_HEALTH_URL}" <<'REMOTE'
set -euo pipefail

remote_dir="$1"
branch="$2"
expected_sha="$3"
app_health_url="$4"
ingress_health_url="$5"

cd "${remote_dir}"
[[ -d .git ]] || { printf 'Remote path is not a Git checkout: %s\n' "${remote_dir}" >&2; exit 2; }
[[ -s .env ]] || { printf 'Remote production .env is missing or empty\n' >&2; exit 2; }
docker volume inspect edge2_pgdata >/dev/null 2>&1 || \
  { printf 'Remote database volume edge2_pgdata is missing\n' >&2; exit 2; }
[[ "$(git branch --show-current)" == "${branch}" ]] || \
  { printf 'Remote deployment is not on branch %s\n' "${branch}" >&2; exit 2; }
[[ -z "$(git status --porcelain)" ]] || \
  { printf 'Remote Git working tree is dirty; refusing to deploy\n' >&2; git status --short >&2; exit 2; }

git fetch origin "${branch}"
git pull --ff-only origin "${branch}"
remote_sha="$(git rev-parse HEAD)"
[[ "${remote_sha}" == "${expected_sha}" ]] || \
  { printf 'Remote HEAD does not match the expected commit\n' >&2; exit 2; }

docker compose --project-name edge2 up -d --build
docker compose --project-name edge2 up -d --force-recreate --no-deps edge2-ingress

healthy=false
for _attempt in {1..30}; do
  if curl --fail --silent --show-error --max-time 5 "${app_health_url}" >/dev/null && \
     curl --fail --silent --show-error --max-time 5 "${ingress_health_url}" >/dev/null; then
    healthy=true
    break
  fi
  sleep 2
done
[[ "${healthy}" == "true" ]] || \
  { docker logs --tail 120 edge2-app >&2 || true; exit 2; }

printf 'EDGE 2.0 app and ingress healthy\n'
printf 'EDGE2_REMOTE_SHA=%s\n' "$(git rev-parse HEAD)"
REMOTE
)"; then
  printf '%s\n' "${remote_output:-Remote deployment failed before producing output}" >&2
  exit 1
fi

printf '%s\n' "${remote_output}"
remote_sha="$(printf '%s\n' "${remote_output}" | awk -F= '/^EDGE2_REMOTE_SHA=/{sha=$2} END{print sha}')"
[[ "${remote_sha}" == "${expected_sha}" ]] || \
  fail "Remote SHA does not match the expected commit"

printf '\nDeployment commit verification\n'
printf 'Local:  %s\n' "${expected_sha}"
printf 'Origin: %s\n' "${origin_sha}"
printf 'Remote: %s\n' "${remote_sha}"
