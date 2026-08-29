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
from app.reconciliation import DerivedStateReconciler, ReconciliationError


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Manually reconcile MRZ derived state from canonical observations."
    )
    mode = command.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Report differences only")
    mode.add_argument("--apply", action="store_true", help="Atomically apply differences")
    command.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
        help="Limit reconciliation to a symbol; may be repeated",
    )
    command.add_argument(
        "--expected-plan-digest",
        help="Refuse apply if the current plan differs from this dry-run digest",
    )
    return command


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.dry_run and arguments.expected_plan_digest:
        parser().error("--expected-plan-digest is valid only with --apply")
    load_local_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2

    reconciler = DerivedStateReconciler(database_url)
    try:
        report = (
            reconciler.dry_run(arguments.symbols)
            if arguments.dry_run
            else reconciler.apply(
                arguments.symbols,
                expected_plan_digest=arguments.expected_plan_digest,
            )
        )
    except ReconciliationError as exc:
        print(
            json.dumps(
                {"mode": "APPLY" if arguments.apply else "DRY_RUN", "error": str(exc)},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
