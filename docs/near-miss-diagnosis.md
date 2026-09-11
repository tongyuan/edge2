# Historical near-miss diagnosis

## Existing architecture retained

The current production near-miss is still the canonical Algorithm A, four
observation, `1.00%` production evaluation. A candidate is actionable only when
it is structurally eligible, is not active, requires more than `1.00%` and no
more than `2.00%`, and belongs to the globally sorted top-five current list.
Its SHA-256 identity binds the evaluator, symbol, route, exact range and
midpoint, supporting observation IDs, newest event, required allowance, and
candidate timestamp.

`current_production_near_miss_episodes` already defines the durable episode
lifecycle used by Web Push. One open row is allowed per symbol/route. Continued
membership remains the same episode even if the candidate changes. Leaving the
current list closes it as `NO_LONGER_CURRENT`; production activation closes it
as `SYMBOL_ACTIVATED`; explicit operator promotion closes it as
`OPERATOR_PROMOTED`. A later re-entry creates a new episode and therefore one
new logical near-miss notification.

The original episode candidate fields remain the immutable entry snapshot used
by the existing notification outbox. Migration 010 adds a separate canonical
snapshot on that row. It is refreshed only during accepted-observation episode
synchronization, never by a report render. The final refresh immediately before
termination is therefore the deterministic episode candidate used by history.
This prevents recalculations from becoming false episodes without changing the
notification payload or identity.

## Diagnosis derivation

Only distinct, trustworthy episodes for the current symbol and current route
are considered. BTD and STR never mix. The current live candidate is appended
to reliable closed episodes in chronological order; the newest five episodes
form the diagnosis window. Earlier trustworthy episodes remain visible in the
detailed API/UI history and are marked outside the current lookback.

Each historical range is compared with the current range using inclusive
intersection:

```text
current_upper >= historical_lower
and current_lower <= historical_upper
```

The current episode counts as one in the displayed recurrence fraction. At
least one historical episode must also overlap, so recurrence is present when
the same-area count is at least two. Partial overlap, containment, and boundary
touching qualify; separated ranges do not.

Allowances remain in chronological order. Each transition is classified with
the diagnosis-only `CONCENTRATION_TREND_EPSILON_PP = 0.02` percentage points:

- delta below `-0.02`: tightening
- delta above `+0.02`: widening
- absolute delta at or below `0.02`: stable

All meaningful tightening transitions (with optional stable transitions) yield
`TIGHTENING`; the equivalent widening sequence yields `WIDENING`; all stable
yields `STABLE`; both directions yield `MIXED`.

The state machine is deliberately categorical:

| Spatial recurrence | Concentration | Diagnosis |
|---|---|---|
| Yes | Tightening | Converging |
| Yes | Stable | Persistent |
| Yes | Widening | Dispersing |
| No | Any | Inconsistent |
| Any | Mixed | Inconsistent |

Fewer than two episodes produces no diagnosis. These outputs are explanatory
history only. They are not inputs to qualification, activation, migration,
promotion eligibility, or Web Push.

## Data audit and backfill decision

The evaluator and database retain exact arbitrary-precision decimals; the
operator surface displays allowance to two decimal places. The repository test
sample includes values such as `1.02`, `1.05`, `1.13`, and `1.126789`, but no
production episode dataset is available in the local workspace to estimate
normal episode-to-episode noise. `0.02` percentage points is therefore a
conservative documented default: a one-hundredth movement such as
`1.08 → 1.07` remains stable. The constant is isolated in
`app/near_miss_diagnosis.py` for later evidence-based adjustment.

Legacy closed episode rows contain only the entry snapshot, so their final
eligible candidates cannot be reconstructed reliably. Migration 010 does not
guess a backfill. Those rows remain marked unreliable and are excluded from
diagnosis. New episodes are trustworthy immediately; an already-open episode
becomes trustworthy on the next accepted-observation synchronization. The API
reports the number of excluded legacy rows.
