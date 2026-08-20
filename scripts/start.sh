#!/usr/bin/env sh
set -eu

python3 scripts/migrate.py
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8790}" --no-access-log
