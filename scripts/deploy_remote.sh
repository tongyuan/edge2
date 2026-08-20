#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${EDGE2_REMOTE_HOST:-tony@100.95.242.17}"
REMOTE_DIR="${EDGE2_REMOTE_DIR:-/home/tony/edge2}"
SSH_KEY="${EDGE2_SSH_KEY:-${HOME}/.ssh/edge_server}"
REMOTE_HEALTH_URL="http://127.0.0.1:${EDGE2_APP_PORT:-8792}/health"
REMOTE_INGRESS_HEALTH_URL="http://127.0.0.1:${EDGE2_INGRESS_PORT:-8793}/health"

if [[ ! -r "${SSH_KEY}" ]]; then
  echo "SSH key is not readable: ${SSH_KEY}" >&2
  exit 2
fi
if [[ -n "$(git -C "${ROOT_DIR}" status --porcelain)" ]]; then
  echo "Deployment requires a clean EDGE 2.0 Git working tree" >&2
  exit 2
fi

ssh_options=(-i "${SSH_KEY}" -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes)
ssh "${ssh_options[@]}" "${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"

rsync -az --checksum --delete \
  --exclude=.git/ \
  --exclude=.env \
  --exclude=.env.local \
  --exclude=backups/ \
  --exclude='*.dump' \
  --exclude=__pycache__/ \
  --exclude='*.pyc' \
  --exclude=.pytest_cache/ \
  --exclude=logs/ \
  -e "ssh -i ${SSH_KEY} -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes" \
  "${ROOT_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

ssh "${ssh_options[@]}" "${REMOTE_HOST}" "test -s '${REMOTE_DIR}/.env'"
ssh "${ssh_options[@]}" "${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && docker compose --project-name edge2 up -d --build"

for attempt in {1..30}; do
  if ssh "${ssh_options[@]}" "${REMOTE_HOST}" \
    "curl --fail --silent --show-error --max-time 5 '${REMOTE_HEALTH_URL}' >/dev/null && curl --fail --silent --show-error --max-time 5 '${REMOTE_INGRESS_HEALTH_URL}'"; then
    echo
    echo "EDGE 2.0 app and ingress healthy"
    exit 0
  fi
  sleep 2
done

ssh "${ssh_options[@]}" "${REMOTE_HOST}" "docker logs --tail 120 edge2-app" >&2 || true
echo "EDGE 2.0 remote health verification failed" >&2
exit 1
