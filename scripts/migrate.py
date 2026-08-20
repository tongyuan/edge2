#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.config import load_local_env
from app.db import apply_migrations


def main() -> int:
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    applied = apply_migrations(database_url)
    print("Applied migrations:", ", ".join(applied) if applied else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
