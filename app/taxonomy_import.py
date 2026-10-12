from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from psycopg2.extras import RealDictCursor

from app.db import connect, transaction
from app.taxonomy import (
    InstrumentTaxonomy,
    TaxonomyValidationError,
    instrument_taxonomy_from_row,
    validate_instrument_taxonomy,
)


CSV_COLUMNS = ("symbol", "asset_class", "sector", "industry")


@dataclass(frozen=True, slots=True)
class ImportIssue:
    row: int
    symbol: str | None
    code: str
    message: str

    def payload(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "symbol": self.symbol,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class TaxonomyImportPlan:
    input_row_count: int
    rows: tuple[InstrumentTaxonomy, ...]
    issues: tuple[ImportIssue, ...]
    changes: tuple[str, ...]
    unchanged: tuple[str, ...]
    before: Mapping[str, Any]

    @property
    def valid(self) -> bool:
        return not self.issues

    def payload(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "input_row_count": self.input_row_count,
            "validated_row_count": len(self.rows),
            "change_count": len(self.changes),
            "unchanged_count": len(self.unchanged),
            "changes": list(self.changes),
            "unchanged": list(self.unchanged),
            "issues": [issue.payload() for issue in self.issues],
            "before": dict(self.before),
            "identity_note": (
                "Exchange-qualified aliases are not supported. Any ':' symbol or "
                "duplicate after canonical normalization is rejected for explicit review."
            ),
        }


def taxonomy_summary(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = [
        instrument_taxonomy_from_row(row, str(row["symbol"]))
        for row in rows
    ]
    asset_classes = Counter(record.asset_class or "UNCLASSIFIED" for record in records)
    return {
        "total": len(records),
        "complete": sum(record.complete for record in records),
        "incomplete": sum(not record.complete for record in records),
        "by_asset_class": dict(sorted(asset_classes.items())),
    }


def read_taxonomy_csv(path: Path) -> tuple[list[InstrumentTaxonomy], list[ImportIssue]]:
    rows: list[InstrumentTaxonomy] = []
    issues: list[ImportIssue] = []
    seen: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            return [], [
                ImportIssue(
                    row=1,
                    symbol=None,
                    code="invalid_columns",
                    message=f"CSV columns must be exactly: {', '.join(CSV_COLUMNS)}",
                )
            ]
        for row_number, raw in enumerate(reader, start=2):
            raw_symbol = str(raw.get("symbol") or "").strip()
            if ":" in raw_symbol:
                issues.append(
                    ImportIssue(
                        row=row_number,
                        symbol=raw_symbol,
                        code="ambiguous_exchange_qualified_symbol",
                        message=(
                            "Exchange-qualified symbols require an explicit reviewed "
                            "mapping to the existing canonical symbol."
                        ),
                    )
                )
                continue
            try:
                taxonomy = validate_instrument_taxonomy(
                    symbol=raw_symbol,
                    asset_class=raw.get("asset_class"),
                    sector=raw.get("sector"),
                    industry=raw.get("industry"),
                    require_complete_equity=True,
                )
            except (TaxonomyValidationError, ValueError) as exc:
                issues.append(
                    ImportIssue(
                        row=row_number,
                        symbol=raw_symbol or None,
                        code="invalid_taxonomy",
                        message=str(exc),
                    )
                )
                continue
            previous_row = seen.get(taxonomy.symbol)
            if previous_row is not None:
                issues.append(
                    ImportIssue(
                        row=row_number,
                        symbol=taxonomy.symbol,
                        code="duplicate_canonical_symbol",
                        message=(
                            f"Canonical symbol duplicates row {previous_row}; "
                            "review identity explicitly."
                        ),
                    )
                )
                continue
            seen[taxonomy.symbol] = row_number
            rows.append(taxonomy)
    return rows, issues


def plan_taxonomy_import(database_url: str, csv_path: Path) -> TaxonomyImportPlan:
    rows, issues = read_taxonomy_csv(csv_path)
    input_row_count = len(rows) + len(issues)
    connection = connect(database_url)
    try:
        connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """
                SELECT symbol, asset_class, sector, industry
                FROM instruments
                ORDER BY symbol ASC
                """
            )
            current_rows = cursor.fetchall()
    finally:
        connection.close()

    current = {
        str(row["symbol"]): instrument_taxonomy_from_row(row, str(row["symbol"]))
        for row in current_rows
    }
    changes: list[str] = []
    unchanged: list[str] = []
    for taxonomy in rows:
        existing = current.get(taxonomy.symbol)
        if existing is None:
            issues.append(
                ImportIssue(
                    row=0,
                    symbol=taxonomy.symbol,
                    code="unknown_symbol",
                    message="Symbol is not registered in the monitored universe.",
                )
            )
        elif existing == taxonomy:
            unchanged.append(taxonomy.symbol)
        else:
            changes.append(taxonomy.symbol)

    return TaxonomyImportPlan(
        input_row_count=input_row_count,
        rows=tuple(rows),
        issues=tuple(issues),
        changes=tuple(sorted(changes)),
        unchanged=tuple(sorted(unchanged)),
        before=taxonomy_summary(current_rows),
    )


def apply_taxonomy_import(database_url: str, csv_path: Path) -> dict[str, Any]:
    plan = plan_taxonomy_import(database_url, csv_path)
    if not plan.valid:
        return {**plan.payload(), "applied": False, "after": dict(plan.before)}

    with transaction(database_url) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            symbols = [row.symbol for row in plan.rows]
            cursor.execute(
                """
                SELECT symbol
                FROM instruments
                WHERE symbol = ANY(%s)
                FOR UPDATE
                """,
                (symbols,),
            )
            locked_symbols = {str(row["symbol"]) for row in cursor.fetchall()}
            if locked_symbols != set(symbols):
                missing = sorted(set(symbols) - locked_symbols)
                raise ValueError(
                    f"instrument set changed after validation; missing: {', '.join(missing)}"
                )
            for taxonomy in plan.rows:
                cursor.execute(
                    """
                    UPDATE instruments
                    SET asset_class = %s,
                        sector = %s,
                        industry = %s,
                        updated_at = CASE
                            WHEN asset_class IS DISTINCT FROM %s
                              OR sector IS DISTINCT FROM %s
                              OR industry IS DISTINCT FROM %s
                            THEN clock_timestamp()
                            ELSE updated_at
                        END
                    WHERE symbol = %s
                    """,
                    (
                        taxonomy.asset_class,
                        taxonomy.sector,
                        taxonomy.industry,
                        taxonomy.asset_class,
                        taxonomy.sector,
                        taxonomy.industry,
                        taxonomy.symbol,
                    ),
                )
            cursor.execute(
                """
                SELECT symbol, asset_class, sector, industry
                FROM instruments
                ORDER BY symbol ASC
                """
            )
            after = taxonomy_summary(cursor.fetchall())

    return {**plan.payload(), "applied": True, "after": after}
