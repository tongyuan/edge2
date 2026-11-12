# EDGE 2.0 Opportunity Intelligence Phase 1

Date: 2026-11-12

## Outcome

Phase 1 is implemented as an additive, deterministic, read-only research projection inside the existing Group Radar. It reconstructs simultaneous BTD and STR hypotheses from canonical schema 4.3 observations, Near Miss episodes, MRZ lifecycle events, and individual Pressure observations without modifying any canonical tracker state.

The operator can select a group candidate, inspect a genuine time–price map, move an “as known at” replay cursor, inspect canonical event details, and read a deterministic opportunity assessment. The implementation never emits BUY/SELL or “Action Now” signals, never triggers an opportunity alert, and keeps entry verification explicitly false.

## Architecture and episode model

- Stable episode IDs are derived from symbol, hypothesis, origin event ID, and rule version.
- BTD and STR hypotheses can coexist for one symbol; opposing evidence remains visible.
- Research vocabulary: Context Observed, Developing, Near Miss, Structure Established, Reassessment, and Historical / Unresolved.
- No observation-count rule was invented for Developing. Near Miss and Structure Established only arise from canonical events.
- Evidence links preserve tracker, event type, canonical ID, price/bounds, effective time, known time, relationship, and sequence order.
- Late packets remain hidden until their receipt time while retaining their original event time.
- Replay cursors are clamped to the database snapshot time, preventing a request from presenting a future knowledge horizon.
- The design is a read-only derived model because Phase 1 has no justified need for persistent opportunity state. This avoids migration and replay-consistency risk while doctrine remains under research.

## API contracts

- `GET /api/opportunities?group_id=<id>&as_known_at=<ISO-8601>` returns universe/group summaries and candidate ordering.
- `GET /api/opportunities/{symbol}?as_known_at=<ISO-8601>` returns episodes, evidence, MRZ lifecycles, Near Miss events, reconstructed individual Pressure observations, replay metadata, OTE availability, and the assessment.
- Both endpoints use one read-only `REPEATABLE READ` database snapshot and return `Cache-Control: no-store`.
- Unknown groups and symbols return 404. Unexpected projection failures return an explicit 503 without changing source records.

## Time–Price Opportunity Map

- X positions use proportional chronological spacing; the Y axis uses a linear instrument-price scale.
- Route/IPDA observations are discrete markers, not fictional continuous history.
- MRZs are translucent bands with exact frozen bounds, activation knowledge time, lifecycle interval, and migration-envelope guides.
- Near Miss zones remain visually provisional and separate from authoritative MRZ bands.
- Every qualifying Pressure observation is plotted at its recorded event time and price. No line implies continuous market-price history.
- Marker selection exposes event time, first-known time, price/bounds, route, IPDA context, MRZ lifecycle, canonical ID, and evidence relationship.
- All/90D/30D navigation and horizontal mobile chart navigation are available.
- OTE is reserved in the legend/model but remains honestly `not_connected`; no OTE marker or price is synthesized.

## Historical replay

Replay refetches the symbol reconstruction using the selected knowledge-time cursor. Future-known observations, Near Miss episodes, MRZ activations, and derived Pressure evidence are omitted. MRZ bounds are never projected before activation, and later lifecycle termination metadata is not exposed before it was known.

Reconstructed latest-four historical Pressure states are labeled `RECONSTRUCTED_AS_KNOWN_AT` and kept separate from prospectively persisted Current Pressure transition events.

## NBIS regression

The general engine fixture verifies the audited NBIS chronology without symbol-specific rules:

- early STR/Premium context appears without an MRZ;
- September BTD and October STR Near Miss evidence both remain visible;
- the STR MRZ appears only at 2 Oct 2026 19:57 UTC knowledge time;
- frozen bounds remain 242.19–243.73 and the migration envelope remains 239.11–246.81;
- 252.90 is Higher, followed by Lower observations at 220.24, 220.85, 201.21, 170.35, and 139.50;
- 13 Oct reconstructs Lower 3/4 and later evidence reconstructs Lower 4/4;
- an 11 Sep replay cannot see the future Near Miss, MRZ, or Pressure evidence;
- no historical OTE marker is present.

## Group Radar integration

- Opportunity counts sit above the existing group evidence.
- Group rows expose research state and leading candidate without introducing a score.
- Selected-group desktop layout uses a group list beside the candidate/map workspace; responsive layouts stack the full workflow.
- Existing IPDA breadth, activity windows, MRZ Migration, Current Pressure, Near Miss, OTE availability, location distribution, event timeline, group members, alerts, and Trade Desk ownership remain intact.
- Group totals deduplicate a symbol within a group and within universe totals while retaining legitimate appearances across multiple groups.

## Files

Created:

- `app/opportunity_intelligence.py`
- `app/static/opportunity-map.js`
- `app/static/opportunity-map.css`
- `tests/test_opportunity_intelligence.py`
- `tests/test_opportunity_intelligence_contract.py`
- `tests/test_opportunity_map.js`
- `design-qa-opportunity-intelligence.md`
- `qa-opportunity-intelligence/group-radar-desktop-final.jpg`
- `qa-opportunity-intelligence/group-radar-mobile-final.jpg`

Modified:

- `app/repository.py`
- `app/api.py`
- `app/static/group-evidence.js`
- `app/static/index.html`
- `app/static/workspace.css`
- `tests/test_api.py`
- `tests/test_group_evidence_contract.py`

## Database migrations

None. The implementation reads existing canonical records and creates no opportunity-owned production rows.

## Verification results

- Deployment-gate suite: 498 non-Pine tests passed.
- Opportunity and Group Radar focused suite: 18 Python tests passed.
- Opportunity Map, workspace derivation, and navigation JavaScript suites passed.
- PostgreSQL API integration test passed, including group filtering and historical replay.
- An earlier full repository run executed 563 tests before the final endpoint integration test was added. The new opportunity, API, database, Group Radar, MRZ, Pressure, notification, and Trade Desk application tests passed. The run retained 21 failures and 20 errors in pre-existing legacy Trade Desk Pine contract tests whose expected script surface does not match the current baseline Pine source; these were not modified or hidden.
- Visual QA passed at 1600 × 1000 and 390 × 844. Candidate selection and replay were exercised with no browser console errors.

Production smoke verification after the explicitly approved rollout confirmed:

- application and database health are `ok`;
- NBIS reconstructs simultaneous STR Reassessment and BTD Near Miss hypotheses;
- the authoritative STR MRZ is 242.19–243.73;
- production exposes 19 qualifying historical Pressure observations for NBIS;
- an 11 Sep replay exposes zero MRZ lifecycles and zero Pressure observations;
- OTE remains `not_connected` and entry verification remains false;
- the production overview contains 11 groups and 74 deduplicated candidate symbols.

## Known limitations

- OTE is not connected.
- Continuous OHLC price history is not present and is not fabricated; this is a structural-event map.
- Sparse IPDA observations remain discrete evidence rather than inferred continuous regimes.
- Developing and Historical / Unresolved are available vocabulary, but no unapproved automatic doctrine promotes or resolves episodes into those states.
- The implementation identifies research/watch candidates only. Entry readiness and profitable outcome are not verified.
- Opportunity state is derived on read; a persistent episode store may become useful only after detection doctrine, correction semantics, and evaluation requirements are approved.

## Proposed next phase

1. Define a canonical OTE event contract and ingest formation, level, touch, invalidation, effective time, and known time.
2. Validate explicit Developing, stale, resolved, and operator-attention doctrines against historical cases before automation.
3. Add outcome/evaluation datasets that do not leak future evidence or convert research state into a trading signal.
4. Profile projection latency as history grows and add targeted indexes or persisted read models only when measurements justify them.
5. Consider opportunity notifications and Trade Desk linkage only under separate operator approval and only after execution-readiness rules are validated.
