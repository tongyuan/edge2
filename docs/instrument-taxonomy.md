# Instrument taxonomy

EDGE taxonomy describes what an instrument is. Saved groups describe what an
operator chooses to trade or monitor. Themes and multiple classifications are
not part of this model.

## Canonical fields

Each monitored symbol has one row in `instruments` with `asset_class`, `sector`,
and `industry`. A null asset class is an allowed rollout placeholder and never
blocks observation ingestion. Sector and industry are corporate classifications
for equities only. Non-equities must leave both fields null.

The allowed asset classes and internally maintained GICS-compatible equity
vocabulary live in `app/taxonomy.py`. The vocabulary is not represented as
official licensed GICS assignment data.

## Reviewed CSV import

Start from `docs/instrument-taxonomy-import.csv` and use exactly these columns:

```csv
symbol,asset_class,sector,industry
```

Dry-run is the default:

```sh
python3 scripts/import_instrument_taxonomy.py reviewed-taxonomy.csv
```

After reviewing the validation report and before/after summary, apply the same
file explicitly:

```sh
python3 scripts/import_instrument_taxonomy.py reviewed-taxonomy.csv --apply
```

The complete file is validated before mutation. Apply mode locks all referenced
instrument rows and updates them in one transaction. Unknown symbols, invalid
asset classes, incomplete equity classifications, non-equity sector/industry
values, exchange-qualified symbols, and duplicate canonical symbols are
rejected without partial updates.

Re-running an unchanged reviewed file is safe and reports its rows as unchanged.
Symbol renaming, alias merging, automatic ticker inference, watchlist edits, and
MRZ or pressure changes are outside this workflow.
