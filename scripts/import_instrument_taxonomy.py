#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.config import load_local_env
from app.taxonomy_import import apply_taxonomy_import, plan_taxonomy_import


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Validate or apply a reviewed EDGE instrument-taxonomy CSV."
    )
    result.add_argument("csv_path", type=Path)
    result.add_argument(
        "--apply",
        action="store_true",
        help="Apply the validated import transactionally. Default is dry-run.",
    )
    result.add_argument(
        "--database-url",
        help="Database URL. Defaults to DATABASE_URL after loading local environment.",
    )
    return result


def main() -> int:
    arguments = parser().parse_args()
    load_local_env()
    database_url = (arguments.database_url or os.getenv("DATABASE_URL", "")).strip()
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    if not arguments.csv_path.is_file():
        print(f"CSV not found: {arguments.csv_path}", file=sys.stderr)
        return 2

    result = (
        apply_taxonomy_import(database_url, arguments.csv_path)
        if arguments.apply
        else {**plan_taxonomy_import(database_url, arguments.csv_path).payload(), "applied": False}
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
