# Deterministic acceptance examples

All examples use IPDA low `100`, high `200`, and full width `100`. Therefore the maximum qualifying concentration span is exactly `1.00`.

## BTD activation with interleaved outliers

Canonical reclaim observations:

```text
110.00
140.00  outlier
110.30
132.00  outlier
110.70
111.00  incoming event
```

The incoming event participates in the sorted price-space seed `110.00, 110.30, 110.70, 111.00`. Span is `1.00 / 100 = 0.01`, so the active MRZ is:

```text
WHO: BTD
lower: 110.00
upper: 111.00
midpoint: 110.50
location: deep_discount_core_mrz
confirming count: 4
```

## Incoming participation prevents old-cluster discovery

Old observations `110.00, 110.20, 110.40, 110.60` form a price concentration. If the incoming event is `130.00`, no newly confirmed cluster may use only the four old events. The incoming event participates in no valid seed, so no activation occurs on that event.

## One percent uses IPDA width

At nominal price near `1000`, observations `1000.00–1001.00` qualify when IPDA width is `100`, because normalized span is `0.01`. The same observations fail when IPDA width is `10`, because normalized span is `0.10`. Nominal symbol price is irrelevant.

## BTD migration

For active bounds `110.00–111.00`, width is `1.00` and the envelope is `108.00–113.00`. Reclaims `120.00, 120.20, 120.40, 120.60` are strictly above the upper boundary and confirm a replacement MRZ `120.00–120.60`. The old `110.00–111.00` bounds remain in the `MRZ_MIGRATED` audit event.

## STR mirror

For active STR bounds `180.00–180.60`, the lower boundary is `178.80`. Rejections `170.60, 170.40, 170.20, 170.00` are below it and confirm the downward successor `170.00–170.60`, classified as `shallow_premium_core_mrz`.

## Zero-width safeguard

Four observations at exactly `110.00` create width `0`. With known tick `0.01`, effective width is `0.01` and the migration envelope is `109.98–110.02`. No arbitrary symbol-percentage fallback is introduced.

These examples are executable assertions in `tests/test_concentration.py` and `tests/test_state_engine.py`. Run `python3 scripts/acceptance_examples.py` for a deterministic JSON summary of the activation/migration examples.
