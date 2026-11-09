# EDGE 2.0 missing-sector metadata audit

## Scope

- Read-only production snapshots from `/api/symbols` and `/api/location-distribution/history?window=20D`.
- Current endpoint: `2026-11-09T05:34:19.283466Z`.
- Comparison endpoint: `2026-10-20T05:34:19.283466Z`.
- Universe: 133 eligible symbols; 129 comparable; 4 unavailable or incomparable.
- No instrument metadata was changed.

## The 55 comparable symbols without sector metadata

| Classification | Count | Interpretation |
| --- | ---: | --- |
| Non-equity instruments | 53 | Sector is intentionally not applicable under the canonical taxonomy model. |
| Equities missing sector | 0 | No 20D-comparable `EQUITY` record lacks sector or industry metadata. |
| Incomplete/unclassified instruments | 2 | `SPCX` and `WDC` have no asset class, sector, or industry and require operator review. |

The 53 non-equity instruments comprise:

- 36 ETFs
- 6 indices
- 7 cryptocurrencies
- 4 commodities

The production payload contains no inconsistent mappings of these forms:

- non-equity instrument with an equity sector: 0
- industry without a sector: 0
- equity with missing sector: 0
- equity with missing industry: 0

## Universe-wide incomplete taxonomy records

The `/api/symbols` payload reports six incomplete taxonomy records:

- `BUG`
- `CIBR`
- `CRWD`
- `HACK`
- `SPCX`
- `WDC`

Only `SPCX` and `WDC` are members of the 20D comparable population. The other four incomplete records are not part of that endpoint-comparable set.

## Conclusion

The large missing-sector count is not primarily an equity-data gap: 53 of 55 records are correctly classified non-equities for which equity-sector classification does not apply. Two comparable records remain genuinely incomplete at the asset-class level. They were not automatically classified because the available evidence does not justify an operator metadata decision.
