#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ ! -r .env ]]; then
  echo "Missing .env" >&2
  exit 2
fi

set -a
source .env
set +a

BACKUP_DIR="${EDGE2_BACKUP_DIR:-/home/tony/edge2-backups}"
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR}/edge2_${timestamp}.dump"
temporary="${target}.tmp"

docker exec edge2-db pg_dump \
  --username "${EDGE2_DB_USER:-edge2}" \
  --dbname "${EDGE2_DB_NAME:-edge2}" \
  --format custom \
  --no-owner \
  > "${temporary}"

test -s "${temporary}"
mv "${temporary}" "${target}"
chmod 600 "${target}"
echo "Backup created: ${target}"
