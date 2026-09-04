# EDGE 2.0

EDGE 2.0 is a small operational MRZ state engine. For each observed symbol its operator monitor answers:

- **SOURCE** — the route that owns the active MRZ: `BTD` or `STR`.
- **ACTIVE MRZ** — the frozen authoritative core MRZ bounds.
- **MRZ LOCATION** — where the active MRZ midpoint sits inside its activation IPDA frame.
- **CURRENT LOCATION** — where the latest observation price sits inside its current IPDA frame.

It is a clean project, database, runtime, and Git repository. It does not import the EDGE 4.2 application or migrate 4.2 records.

## Operational doctrine

Every symbol begins as `NO_ACTIVE_MRZ`. A route becomes authoritative only when an incoming schema 4.3 observation completes a valid four-observation price concentration. The authority is singular:

```text
SOURCE = active_mrz.route_owner
```

The active bounds are frozen. Later observations cannot resize them. A confirmed external successor concentration can atomically replace them using its own BTD/STR route and structural validity, independently of the previous authority's route or direction. A route-changing migration records `MRZ_MIGRATED` followed by the `ROUTE_CHANGED` audit companion.

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

The same geometry classifies the latest observation independently of MRZ
authority. It returns deep/shallow discount or premium within the current IPDA
range, `below_ipda_range` or `above_ipda_range` outside it, and `null` at exact
EQM rather than inventing another location bucket.

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

- Observations inside the inclusive envelope do not trigger migration.
- An incoming external observation evaluates only its own higher/lower side and BTD/STR route pool.
- Either route may succeed on either external side when the candidate passes its own structural-validity rule: BTD in Discount or STR in Premium.
- Successor evidence is filtered from the incoming route's rolling 20-event window and uses the identical concentration algorithm, including newest-observation participation.
- Inside-envelope events still age older successor evidence out of that window.
- Migration replaces `active_mrz` and writes the old/new bounds to `mrz_events` in one database transaction.

## Deterministic ordering and replay

Observations are immutable and ordered by `observed_at`, then `received_at`, then database insertion ID. Event ID text is never used as chronology. After every accepted event, the affected symbol is replayed from durable observations and its derived active row plus transition audit are atomically reconciled. Late delivery, process restart, and deterministic replay therefore converge to the same state.

Derived-state maintenance after an intentional production-rule change is manual only:

```text
python3 scripts/reconcile_derived_state.py --dry-run
python3 scripts/reconcile_derived_state.py --apply --expected-plan-digest <dry-run-plan-digest>
```

The dry run is read-only. Apply replays canonical observations through the production state engine, takes per-symbol advisory locks, replaces only differing `active_mrz` and `mrz_events` state in one verified transaction, and never modifies observations. This command is not called by startup, deployment, scheduling, or the UI.

## API and MRZ Monitor

```text
GET  /health
POST /webhook/tradingview
GET  /api/symbols
GET  /api/symbols/{symbol}
GET  /api/symbols/{symbol}/mrz
GET  /api/groups
POST /api/groups
GET  /api/groups/{group_id}
PUT  /api/groups/{group_id}
DELETE /api/groups/{group_id}
GET  /api/groups/{group_id}/migration-path
GET  /api/diagnostics/activation-feasibility
GET  /api/diagnostics/mrz-robustness
GET  /api/notifications/config
POST /api/notifications/subscriptions
DELETE /api/notifications/subscriptions
GET  /api/notifications/events
GET  /
GET  /diagnostics/activation-feasibility
GET  /diagnostics/mrz-robustness
```

The product surfaces have deliberately separate responsibilities:

- **MRZ Monitor** shows production WHO + WHERE and the current authoritative MRZ.
- **MRZ Formation Diagnostics** shows the current production formation rule,
  observed coverage, first qualifications, and pre-activation near misses without
  changing production state.
- **MRZ Operation Card** explains post-activation robustness, migration pressure,
  successor watch, and discretionary operator evidence.
- **Pine strategy tool** handles execution only after the operator chooses which
  strategy to arm.

MRZ Monitor fetches one latest-row overview and fetches detail only after
selection. Its Location Heatmap groups every symbol by `current_price_location`
into the four primary IPDA locations, with visually secondary below-range,
above-range, and unavailable groups. Symbols remain visible without an active
MRZ, and their chips reuse the existing selected-symbol detail loader. A small
filled dot marks only overview rows whose authoritative `mrz_status` is
`active`; it never changes bucket placement or exposes route ownership.

Group Tracking saves named symbol cohorts without owning any market state.
`Current State` derives its location distribution from the same latest-observation
classifier, counts authority directly from `active_mrz`, and classifies each
member by its latest canonical `MRZ_MIGRATED` midpoint change. `Migration Path`
reads the current `MRZ_ACTIVATED`/`MRZ_MIGRATED` chain by `occurred_at` and uses
the structural location persisted on each historical event. Saving, editing, or
deleting a group never writes observations, active authority, or MRZ events.

The selected detail renders SOURCE, ACTIVE MRZ, MRZ LOCATION, CURRENT LOCATION,
active-core supporting evidence, latest observation, and MRZ status. Both
overview and detail derive `current_price_location` through the same backend
classifier using the latest accepted observation price and that observation's
IPDA 20W frame. CURRENT LOCATION adds a display-only whole-percentage depth
from EQM toward the relevant IPDA boundary, or explicit EQM/out-of-range text.
This does not alter shallow/deep classification.

LATEST OBSERVATION combines the latest price, route, observation type, and
canonical `observed_at`. Its operator timestamp is formatted in the fixed
TradingView timezone as `DD Mon YYYY · HH:MM UTC−4`; it never substitutes
delivery, database-write, refresh, activation, or migration time. The display
offset never varies for daylight saving time or the browser, Mac, and server
timezones.

`supporting_observation_count` starts with the observations in the confirming
cluster. During that active MRZ's lifetime it increases only for accepted,
deduplicated observations on the owning route that remain structurally eligible
and fall inside the frozen core bounds. Observations elsewhere in the migration
envelope, successor candidates, and opposite-route observations do not count.
The count is cumulative rather than rolling-window progress, and a migrated MRZ
starts from its own confirming cluster without inheriting the old count.
For every activation or migration, formation start, completion, and duration
come from the earliest and latest `observed_at` values in the exact final
confirming `Cluster.members`. They remain supporting evidence only and are
stored with the active row plus old/new transition audit state. The additive
migration leaves pre-existing rows null rather than guessing historical values.

Before activation, Evidence reports `No qualifying concentration` and the raw
BTD reclaim/STR rejection counts retained in the two route-specific latest-20
windows. These counts are visibility, not progress, ownership, prediction, or
candidate bounds.

## Clean database

The PostgreSQL 16 database revolves around:

- `observations` — validated, durable, deduplicated schema 4.3 events.
- `active_mrz` — one authoritative row per symbol.
- `mrz_events` — operational transition audit only.
- `ingestion_rejections` — sanitized invalid-packet diagnostics.
- `ingestion_metrics` — lightweight durable counters for health reporting.
- `web_push_subscriptions` — single-operator browser Push subscriptions.
- `web_push_notifications` — deduplicated logical activation and migration notifications.
- `web_push_delivery_attempts` — isolated per-subscription delivery outcomes.
- `web_push_notification_cutovers` — replay-safe migration notification cutover.
- `saved_symbol_groups` — named canonical symbol cohorts only; analytics remain derived.

Migration `001_initial.sql` builds the isolated schema. Additive migrations
`002–007` add the overview index, supporting count, nullable immutable
formation evidence, downstream Web Push tables, and migration-notification
provenance/cutover state, plus saved cohort definitions. No 4.2 table or historical
record is read. See [`docs/web-push.md`](docs/web-push.md) for notification
configuration, safety, deployment, and iPhone verification.

## Test

Tests run in an isolated, temporary PostgreSQL container and remove its volume afterward:

```bash
make test
```

The suite covers ingestion, validation, durable duplicate handling, price-space
concentration, route windows, directional IPDA context, exact-cluster formation
duration, activation, frozen bounds, migration, zero-width tick safety, late
replay, atomic audit preservation, API output, UI presentation, and restart
persistence.

## Git development and remote operation

The Mac is the only normal development and Git-authoring workspace. The public
repository at `https://github.com/tongyuan/edge2` is the canonical source-code
history. The remote server is a read-only Git consumer and the sole operational
runtime:

```text
/Users/tonywong/edge2 -> GitHub public main -> /home/tony/edge2
```

From clean local `main`, test, push, pull the exact commit, restart the runtime,
and verify health plus SHA equality with:

```bash
./scripts/deploy-remote.sh
```

Source is never normally copied to the server with `rsync`, `scp`, or archives.
The remote production `.env`, database volume, observations, MRZ state, and
backups never travel through Git.

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

EDGE 2.0 has no EQM workflow payload, chronology product, MFE/MAE, excursion analysis, acceptance scoring, readiness, recommendations, suggested or operator handover, approval, manual MRZ activation, allocation mandate, research queue, candidate engine, macro or sector gate, or Athena interpretation.

## Environment

Copy `.env.example` to `.env` only on the remote server and replace every secret. Never commit `.env`.
