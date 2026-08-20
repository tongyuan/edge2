# EDGE 2.0

EDGE 2.0 is a small operational MRZ state engine. For each observed symbol it answers only:

- **WHO** — the route that owns the active MRZ: `BTD` or `STR`.
- **WHERE** — the frozen active core MRZ bounds, midpoint, and IPDA 20-week structural location.

It is a clean project, database, runtime, and Git repository. It does not import the EDGE 4.2 application or migrate 4.2 records.

## Operational doctrine

Every symbol begins as `NO_ACTIVE_MRZ`. A route becomes authoritative only when an incoming schema 4.3 observation completes a valid four-observation price concentration. The authority is singular:

```text
WHO = active_mrz.route_owner
```

The active bounds are frozen. Later observations cannot resize them. Only a confirmed same-route successor concentration can atomically replace them.

Cross-route replacement has no unambiguous trigger in the frozen first-build doctrine. It is isolated in `evaluate_cross_route_replacement()` and deliberately returns no replacement.

## Schema 4.3 webhook contract

`POST /webhook/tradingview`

```json
{
  "schema_version": "4.3",
  "event_id": "unique-event-id",
  "symbol": "SPXUSDT",
  "route": "BTD",
  "observation_type": "reclaim",
  "observation_price": 0.4321,
  "ipda_20w_high": 0.7000,
  "ipda_20w_low": 0.2000,
  "observed_at": "2026-08-20T12:00:00Z",
  "webhook_secret": "deployment-secret"
}
```

`STR` requires `observation_type = rejection`. Authentication may instead use `X-EDGE2-Webhook-Secret` or `Authorization: Bearer ...`. The secret is redacted from rejection diagnostics and is never stored with accepted observations.

Validation is exact: supported schema, required unique event ID, normalized symbol, route/type match, finite positive observation price, finite valid IPDA range, and timezone-aware timestamp. PostgreSQL's unique `event_id` constraint is the durable idempotency boundary. A retry returns HTTP 200 as a duplicate no-op.

The isolated Pine v6 route emitter is
[`pine/EDGE_2_ROUTE.pine`](pine/EDGE_2_ROUTE.pine). It retains the proven 4.2
IPDA/BTD/STR trigger mechanics but emits only the exact schema 4.3 structural
observation at trigger close. See
[`docs/pinescript-route-emitter.md`](docs/pinescript-route-emitter.md) for the
source audit and [`docs/tradingview-cutover.md`](docs/tradingview-cutover.md) for
the manual, non-destructive alert cutover.

## IPDA 20-week geometry

```text
ipda_width       = ipda_20w_high - ipda_20w_low
eqm              = (ipda_20w_high + ipda_20w_low) / 2
discount_midpoint = (ipda_20w_low + eqm) / 2
premium_midpoint  = (eqm + ipda_20w_high) / 2
```

BTD midpoint boundaries:

```text
[IPDA LOW, discount midpoint) => deep_discount_core_mrz
[discount midpoint, EQM)      => shallow_discount_core_mrz
```

STR midpoint boundaries:

```text
(EQM, premium midpoint]       => shallow_premium_core_mrz
(premium midpoint, IPDA HIGH] => deep_premium_core_mrz
```

EQM itself belongs to neither route. BTD concentrations in premium and STR concentrations in discount are invalid.

## Concentration engine

Each symbol maintains independent canonical rolling windows of the latest 20 BTD reclaims and latest 20 STR rejections. There is no elapsed-time expiry. Outliers can sit between qualifying observations.

```text
normalized_span = (highest observation - lowest observation) / full IPDA 20W width
qualifies       = observation_count >= 4 and normalized_span <= 0.01
```

`0.01` means one percent of the full IPDA range, never one percent of nominal symbol price.

For every incoming event the engine sorts the eligible route window by price, inspects each contiguous four-observation seed, retains seeds at or below the threshold that contain the incoming event, selects the tightest seed, then expands to adjacent price observations while the complete span remains valid. Bounds are the actual observed minimum and maximum; no padding, averaging, volatility band, or behavior weighting exists.

The confirming event's IPDA frame supplies normalization and structural classification. This is explicit and deterministic when the IPDA frame changes between observations.

## Activation and migration

Activation persists the owner, bounds, midpoint, location, evidence count, confirming time/event, activation IPDA frame, normalized span, and instrument tick.

For active width `W`:

```text
effective_W = max(W, instrument tick)
lower boundary = core lower - 2 * effective_W
upper boundary = core upper + 2 * effective_W
```

The tick comes from an authoritative `EDGE2_SYMBOL_TICKS_JSON` override when configured; otherwise it is the smallest decimal quantum carried by the confirming prices.

- Same-route observations inside the inclusive envelope are volatility and do not change state.
- BTD successor evidence must be strictly above the upper boundary.
- STR successor evidence must be strictly below the lower boundary.
- Successor evidence is filtered from the route's rolling 20-event window and uses the identical concentration algorithm.
- Inside-envelope events still age older successor evidence out of that window.
- Migration replaces `active_mrz` and writes the old/new bounds to `mrz_events` in one database transaction.

## Deterministic ordering and replay

Observations are immutable and ordered by `observed_at`, then `received_at`, then database insertion ID. Event ID text is never used as chronology. After every accepted event, the affected symbol is replayed from durable observations and its derived active row plus transition audit are atomically reconciled. Late delivery, process restart, and deterministic replay therefore converge to the same state.

## API and Symbol Lab

```text
GET  /health
POST /webhook/tradingview
GET  /api/symbols
GET  /api/symbols/{symbol}
GET  /api/symbols/{symbol}/mrz
GET  /
```

Symbol Lab fetches the symbol list once and fetches detail only after selection. It renders WHO, WHERE, structural location, confirming evidence, latest observation, and MRZ status. It contains no chronology, lifecycle, research, recommendation, readiness, approval, or handover interface.

## Clean database

The PostgreSQL 16 database revolves around:

- `observations` — validated, durable, deduplicated schema 4.3 events.
- `active_mrz` — one authoritative row per symbol.
- `mrz_events` — operational transition audit only.
- `ingestion_rejections` — sanitized invalid-packet diagnostics.
- `ingestion_metrics` — lightweight durable counters for health reporting.

Migration `001_initial.sql` builds a new schema. No 4.2 table or historical record is read.

## Test

Tests run in an isolated, temporary PostgreSQL container and remove its volume afterward:

```bash
make test
```

The suite covers ingestion, validation, durable duplicate handling, price-space concentration, route windows, IPDA boundaries, activation, frozen bounds, migration, zero-width tick safety, late replay, atomic audit preservation, API output, and restart persistence.

## Remote-only operation

The Mac is a development/Git workstation, not an operational EDGE 2.0 runtime. The deployed source of truth is `/home/tony/edge2` on the remote server.

```text
edge2-app  -> 127.0.0.1:8792
edge2-ingress -> 127.0.0.1:8793 -> edge2-app
edge2-db   -> 127.0.0.1:5435
volume     -> edge2_pgdata
```

The existing ngrok hostname is routed to `edge2-ingress` after the operator
confirmed that 4.2 alerts were defunct. The preserved EDGE 4.2 application,
containers, Redis, and data remain unchanged. See [Remote operations](docs/operations.md), [Backup and restore](docs/backup-restore.md), and [TradingView cutover](docs/tradingview-cutover.md).

## Deliberately removed 4.2 features

EDGE 2.0 has no EQM workflow payload, behavior tracking, chronology product, lifecycle tracking, MFE/MAE, excursion analysis, acceptance scoring, readiness, recommendations, suggested or operator handover, approval, manual MRZ activation, allocation mandate, research queue/diagnostics, candidate engine, macro or sector gate, Athena interpretation, historical behavior comparison, or post-activation behavior tracking.

## Environment

Copy `.env.example` to `.env` only on the remote server and replace every secret. Never commit `.env`.
