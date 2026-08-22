# Deterministic state architecture

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

Formation evidence is derived at that same construction boundary from the
exact final cluster members: earliest canonical `observed_at`, latest canonical
`observed_at`, and their difference in seconds. Supporting observations cannot
change it. Activation and migration audit rows retain the new formation values;
migration rows also retain the old MRZ's values. Nullable additive columns keep
historical rows explicitly unavailable rather than assigning a guessed zero.

## Cross-route boundary

The data and transition model support a future `ROUTE_CHANGED` event. The first build does not guess at the trigger: `evaluate_cross_route_replacement()` is a small explicit no-op until a separate frozen doctrine defines legitimate opposite-route authority replacement.
