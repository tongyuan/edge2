#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: EDGE2_ALLOW_RESTORE=YES scripts/restore.sh /absolute/path/edge2_TIMESTAMP.dump" >&2
  exit 2
fi
if [[ "${EDGE2_ALLOW_RESTORE:-}" != "YES" ]]; then
  echo "Restore refused. Set EDGE2_ALLOW_RESTORE=YES after verifying the target backup." >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"
source .env

backup_path="$1"
if [[ "${backup_path}" != /* || ! -s "${backup_path}" ]]; then
  echo "Backup must be a non-empty absolute file path" >&2
  exit 2
fi

docker compose stop edge2-app
docker exec -i edge2-db pg_restore \
  --username "${EDGE2_DB_USER:-edge2}" \
  --dbname "${EDGE2_DB_NAME:-edge2}" \
  --clean \
  --if-exists \
  --no-owner \
  < "${backup_path}"
docker compose up -d edge2-app

echo "Restore completed from ${backup_path}"
