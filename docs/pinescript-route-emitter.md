# EDGE 2.0 Pine route emitter

## Source isolation and audit

The new operational emitter is `pine/EDGE_2_ROUTE.pine`. It was forked from the
locally canonical EDGE 4.2 route source without modifying that source.

```text
EDGE 4.2 source: /Users/tonywong/Documents/New project/pine/edge_route_behavior.pine
Pine version:    6
Original lines:  1,041
Original SHA256: 35f44eac42fb1c0640eb6f4398b36712070a2e55c4ce18ff9eb8054a55f0ad8d
EDGE 2.0 source: /Users/tonywong/edge2/pine/EDGE_2_ROUTE.pine
EDGE 2.0 lines:  429
Reduction:        612 lines (58.8%)
```

The 4.2 source is untracked in its already-dirty worktree. Its checksum above is
the immutable audit reference used during this fork. No file in the 4.2 project
was edited, renamed, or deleted.

## Preserved operational logic

- The 100-bar EQM20 source, smoothing, standard-deviation band, and mirrored
  bull/bear retest state machines are unchanged in behavior.
- The IPDA 20-week low and high remain weekly `ta.lowest(low, 20)` and
  `ta.highest(high, 20)` values requested with the chart ticker ID.
- BTD still arms only on the bearish detector's first meaningful drop while the
  market is in IPDA discount. It requires the first dip below EQM20 -1 and then
  a directional close back above that band.
- STR still arms only on the bullish detector's first meaningful bounce while
  the market is in IPDA premium. It requires the first rip above EQM20 +1 and
  then a directional close back below that band.
- The 240-bar arm cooldown, 60-bar first-structure window, 1-minute profile
  gate, IPDA location gate, and old 240-bar post-trigger re-arm boundary remain.
- Arm, first dip/rip, reclaim/reject labels and the EQM20/+1/-1 plots remain.

The only intentional timing change is alert delivery. EDGE 4.2 stored the
trigger's exact price and timestamp, then emitted a research packet 240 bars
later. EDGE 2.0 emits its structural observation on that trigger bar using the
same captured `close` and `time_close`.

## Removed systems

The fork contains no BTD/STR post-trigger residency counters, excursion or
MFE/MAE measurement, location-quality scoring, EQM transition episode,
re-entry/escape tracking, research completion, lifecycle payload, debug output,
or behavior payload. Unused master/regime/pressure calculations and the
research-only IPDA transition-zone chart fill were also removed.

## Schema 4.3 examples

BTD reclaim:

```json
{"schema_version":"4.3","event_id":"BINANCE:BTCUSDT|4.3|BTD|reclaim|1767225660000","symbol":"BTCUSDT","route":"BTD","observation_type":"reclaim","observation_price":91234.5,"ipda_20w_high":108000.0,"ipda_20w_low":49000.0,"observed_at":"2026-01-01T00:01:00Z"}
```

STR rejection:

```json
{"schema_version":"4.3","event_id":"NASDAQ:NVDA|4.3|STR|rejection|1767225720000","symbol":"NVDA","route":"STR","observation_type":"rejection","observation_price":181.375,"ipda_20w_high":195.95,"ipda_20w_low":86.62,"observed_at":"2026-01-01T00:02:00Z"}
```

The event ID is deterministic from exchange-qualified symbol, schema, route,
observation type, and the confirmed trigger's `time_close`. Prices serialize at
the instrument's minimum-tick precision. EQM is calculated internally for route
logic but is not sent.

## Alert separation

TradingView snapshots script inputs when an alert is created. Use the two alert
routing inputs to make independent alerts:

1. For BTD, enable **Emit BTD Reclaim Observations**, disable **Emit STR
   Rejection Observations**, and select **Any alert() function call**.
2. For STR, disable BTD, enable STR, and create a second alert using the same
   condition.

Each trigger branch contains one `alert()` call with
`alert.freq_once_per_bar_close`. There is no debug or lifecycle alert path.

## Verification

On 2026-08-20 the complete local source was submitted to TradingView's Pine v6
compiler with **Add to chart** and compiled successfully. The temporary chart
instance was removed immediately. No TradingView script, layout, or alert was
saved, published, created, edited, or deleted during verification.
