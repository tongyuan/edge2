# Deterministic state architecture

## Product surfaces

- **MRZ Monitor** exposes production WHO + WHERE and the current authoritative
  active MRZ.
- **MRZ Formation Diagnostics** replays the current production formation rule,
  first qualifications, and pre-activation near misses. Only an explicit
  confirmation on an exact current card can invoke the operator-promotion
  command.
- **MRZ Operation Card** presents post-activation robustness, migration pressure,
  successor evidence, and discretionary operator context.
- **Pine strategy tool** remains the execution layer after an operator selects a
  strategy to arm.

## Transaction path

1. Parse JSON and authenticate using constant-time secret comparison.
2. Validate the exact schema 4.3 contract and normalize the symbol.
3. Take a PostgreSQL transaction-scoped advisory lock for that symbol.
4. Insert the immutable observation with `ON CONFLICT (event_id) DO NOTHING`.
5. Return a successful duplicate no-op when the unique event already exists.
6. Replay that symbol in canonical time order from database observations.
7. Replace its derived `mrz_events` rows and upsert or remove its single `active_mrz` row.
8. Update operational counters and commit once.

The active authority and the transition that produced it are never committed separately.

Near-miss episode reconciliation runs in the same accepted-observation
transaction after derived authority is replaced. A dedicated transaction-level
advisory lock serializes the global top-five `Current production near misses`
membership. Existing membership is a continuing episode; a newly entering
symbol-route creates one durable deliverable episode; exit closes it. On first
post-migration processing, candidates that were already present in the prior
canonical snapshot are stored as non-deliverable baselines so restart or replay
cannot manufacture notifications.

## Operator promotion transaction

1. Normalize the symbol and take its normal advisory lock.
2. Reject an existing authoritative MRZ, except an exact repeated promotion
   command, which returns an idempotent success.
3. Re-read canonical observations and active symbols inside the transaction.
4. Recompute the same A-4-1, structurally eligible, `>1.00%` and `<=2.00%`,
   sorted-and-capped current near-miss list used by the operator page.
5. Require exact symbol, route, and SHA-256 candidate-identity equality.
6. Insert the immutable promotion record, seed canonical replay at its trigger,
   and persist `MRZ_ACTIVATED` plus `active_mrz` atomically.
7. Close the corresponding near-miss episode as `OPERATOR_PROMOTED`.

Candidate identity binds evaluator version, symbol, route, exact bounds and
midpoint, supporting observation identities, newest observation, required
allowance, and candidate time. It is an optimistic-concurrency token, not a
replacement for server-side evaluation.

## Canonical order

```text
observed_at ASC, received_at ASC, observations.id ASC
```

`observed_at` is market observation time. `received_at` explains delayed delivery and breaks equal observation timestamps. The database ID breaks the remaining tie. An `event_id` name never implies chronology.

## Rolling window and late events

Replay holds two independent deques per symbol, each capped at 20. A new valid event is appended only to its route deque. This makes the event #21 aging rule exact and lets inside-envelope events age successor evidence even though those events are not successor-eligible.

A late packet is inserted with its real `observed_at`, then the symbol is replayed. Derived state may therefore reconcile to the state that canonical delivery would have produced. This behavior is intentional.

## Deterministic cluster ties

Seed selection orders by raw span, lower price, upper price, and canonical member order. Expansion chooses the adjacent addition with the smallest resulting complete span; exact ties prefer the lower-price side and then canonical order. These tie rules add no market threshold and make replay stable.

## Frozen bounds

An active MRZ is constructed once from the confirming cluster. No later evidence mutates its bounds or activation metadata. A successor constructs a new immutable MRZ and replaces the active row while the transition retains the former bounds.

For an operator-promoted authority, a later full-route production evaluation
may independently satisfy the unchanged 1.00% rule while remaining ineligible
for migration. The first such result is retained with its actual qualified
bounds, midpoint, route, location, time, threshold, and supporting observation
identities as `Production Confirmation`. It does not alter authority or emit a
second activation. Replay stops confirmation search at the first genuine
migration trigger, after which the existing successor becomes authoritative in
the normal way. Successor construction carries the lifecycle's immutable
activation source forward; `MRZ_MIGRATED` is not a second activation and does
not relabel an `OPERATOR_PROMOTED` origin.

Formation evidence is derived at that same construction boundary from the
exact final cluster members: earliest canonical `observed_at`, latest canonical
`observed_at`, and their difference in seconds. Supporting observations cannot
change it. Activation and migration audit rows retain the new formation values;
migration rows also retain the old MRZ's values. Nullable additive columns keep
historical rows explicitly unavailable rather than assigning a guessed zero.

## Cross-route boundary

The data and transition model support a future `ROUTE_CHANGED` event. The first build does not guess at the trigger: `evaluate_cross_route_replacement()` is a small explicit no-op until a separate frozen doctrine defines legitimate opposite-route authority replacement.
