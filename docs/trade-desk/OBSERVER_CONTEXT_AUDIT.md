# TD_1.0 observer-context audit — 18 Sep 2026

## Outcome and evidence boundary

Audited source: [`pine/TradeDesk.pine`](../../pine/TradeDesk.pine).
Source SHA-256 at audit: `27e661a86d494aad7ec2a5f9e335c890e1153187744694e3d59ba5a90ffd0d54`.

The current source already has one canonical geometry, one context identity,
and one anchor/path state machine. No same-instance stale-table bug was found.
No Pine behavior or payload schema was changed on the strength of an unproven
hypothesis.

The supplied values cannot describe one execution of this source:

- Alert current midpoint 102.15 is serialized from `currentMrzMidpoint`.
- Table `CURRENT MIDPOINT @ 101.49` uses the same `currentMrzMidpoint` through
  the freshly derived lower-adjacent anchor, not a cached boundary or other
  timeframe value.
- With current 102.15 and previous 103.83, the derived migration is `LOWER`,
  not `HIGHER`, and Migration EQM is 102.99.
- Alert and table share `observerObservedPathSteps`, last reached anchor,
  and last contact state. There is no table-specific counter or anchor cache.
- The current anchor-transition payload has no `previous_reached_anchor`
  field. The previous reached anchor is in the table and label tooltips.
  A raw payload containing that field would require a different source version.

**Proven:** the reported geometry does not come from the same execution/context
of the audited source. **Not proven:** which live indicator or alert instance,
input set, source version, or observation time accounts for the mismatch.
The actual chart inputs, running-alert configuration, screenshots, and raw
payloads were not included in this audit request.

TradingView runs an alert using a saved copy of the script, inputs, chart symbol,
and timeframe taken at alert creation. Later changes on the chart do not update
that alert. This is a documented mechanism that explains independent contexts;
it is not evidence identifying the particular alert in this case.
[TradingView: Alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/).

The code proves the origins of the two midpoint fields, but not the exact input
bounds that produced them. It cannot identify 101.49 as an old slot, pre-swap
slot, or other symbol without the missing settings. A different symbol/run,
saved alert configuration, script version, or screenshot time must be reconciled
before assigning a more specific root cause. Different datasets/replay starts
can also yield different path counts even for identical geometry.

## Canonical MRZ context and existing reset guard

Slot A is current when `activeMrzSlot == "A"`; otherwise Slot B is current.
The other slot is previous. There is no separate swap toggle or hidden swap
state. Selecting the other active slot swaps all three authoritative values:
upper, lower, and activation timestamp.

Canonical geometry is derived every execution:

```text
current midpoint  = round_to_mintick((current upper + current lower) / 2)
previous midpoint = round_to_mintick((previous upper + previous lower) / 2)
Migration EQM     = round_to_mintick((current midpoint + previous midpoint) / 2)
MRZ Migration     = HIGHER / LOWER / COINCIDENT by the two rounded midpoints
```

Existing `observerStructureChanged` compares the stored identity with:

- `activeMrzSlot`
- standardized `configuredTickerId`
- current lower, upper, activation timestamp
- previous lower, upper, activation timestamp

There is no price or bar-time component. The midpoints are derived from the bounds,
so storing a second midpoint identity is unnecessary. Chart ticker is checked
against the configured ticker by `symbolMatches`; a mismatch removes geometry
and clears state. The chart timeframe is a Pine runtime context, not a changing
series field that needs a second identity model.

| Change | Existing behavior |
| --- | --- |
| Current/previous bounds or activation input | Pine recalculates the matching input context; existing identity guard resets on the first available confirmed bar. |
| Active slot / current-previous swap | Both geometries are re-derived; active-slot and bound/timestamp identity components differ; reset/baseline applies. |
| Configured ticker | Matching context recalculates; mismatch clears state; matching new ticker establishes a new identity. |
| Chart symbol | New runtime dataset/context; mismatching configured symbol clears state. |
| Chart timeframe | Matching execution context restarts or is restored by Pine; replay uses that timeframe's bars. Counts need not equal the old timeframe's counts. |
| Wrong symbol, invalid bounds, observer disabled, or before current activation | All observer state is cleared, identity removed, labels deleted; no anchor alerts. |

When geometry is unavailable, reset occurs immediately. When available and the
identity changes, the confirmed-bar branch clears path/contact state, stores
the new identity, deletes old observer labels, and baselines contacts already
present on that reset bar. Those baseline contacts are deliberately not emitted.
This prospective baseline semantics was preserved.

Reset includes state, last/previous anchors, contact mask/summary, last timestamp
and bar, path count, distinct EQM contact count, second-EQM eligibility, all three
active-contact episode flags, and observer labels. Upper/lower adjacent anchors
are nonpersistent and are rebuilt each execution.

Pine input values are fixed during a run. Input changes trigger recalculation;
matching settings can use runtime caching, and chart reload clears cached data.
This does not turn derived geometry into a stale `var` value.
[TradingView: Execution model](https://www.tradingview.com/pine-script-docs/language/execution-model/).

## Output-to-state trace (before any code change)

Line references are for the audited source; names are authoritative.
`R` below means geometry unavailable (434–460), or context changed on a confirmed
bar (466–494).

| Field | Source variable | Persistent / derived | Update location / reset | Alert use | Table use |
| --- | --- | --- | --- | --- | --- |
| current_mrz_midpoint | `currentMrzMidpoint` | Derived | Slot selection 103–109; midpoint 139; re-derived each execution | Transition and second-EQM payloads | Adjacent-anchor value; same plot value |
| previous_mrz_midpoint | `previousMrzMidpoint` | Derived | Slot selection 103–109; midpoint 140; re-derived each execution | Transition and second-EQM payloads | Adjacent-anchor value; same plot value |
| migration_eqm | `migrationEqm` | Derived | Rounded midpoint formula 144; re-derived each execution | Transition and second-EQM payloads | Adjacent-anchor value |
| migration_direction | `observerMrzMigration` | Derived, not `var` | Midpoint comparison 394; unavailable if either MRZ unavailable | No such payload field | MRZ Migration |
| upper_anchor | `observerUpperAdjacentAnchor`, `observerUpperAdjacentPrice` | Derived | Initialized empty 353–356; nearest strictly above close 358–373 | Not in payload | Upper Anchor |
| lower_anchor | `observerLowerAdjacentAnchor`, `observerLowerAdjacentPrice` | Derived | Initialized empty 353–356; nearest strictly below close 375–389 | Not in payload | Lower Anchor |
| current_contact | `observerContactSummary`, then `observerLastContactSummary` and mask | Event-local / persistent | Fresh confirmed contact 504–521; persistent values R | `current_contact`, mask | Last Contact = persistent last-contact summary |
| previous_contact | `observerPriorContactSummaryForEvent`, mask | Event-local snapshot of persistent state | Captured before contact mutation 506–507; event-local defaults each execution | `previous_contact`, mask | No equivalent row; Previous Reached Anchor is a different field |
| last_reached_anchor | `observerLastReachedAnchor` | Persistent `var` | Promoted 510 on every raw contact; R | `last_reached_anchor` | Last Reached Anchor |
| previous_reached_anchor | `observerPreviousReachedAnchor` | Persistent `var` | Copies old last anchor at 509; R | Not in current schema; label tooltips only | Previous Reached Anchor |
| path_step | `observerObservedPathSteps` | Persistent `var` | Increment 514 once per fresh contact set; R | Transition and second-EQM payloads | Path Step # |
| distinct_eqm_contacts | `observerEqmDistinctContactCount` | Persistent `var` | Increment 516 for fresh EQM contact; R | Second-EQM payload `eqm_contact_count` | Distinct EQM Contacts |
| last_contact_at | `observerLastReachedAt` | Persistent `var`, UTC epoch milliseconds | Assigned `time_close` at 512; R | Numeric `observed_at` | Last Contact At, formatted in fixed UTC−4 only |

The table does not display all three midpoint values in dedicated rows. Its
adjacent anchor rows display whichever canonical anchors surround the current
close. Current close can change those adjacent rows without changing the last
confirmed contact/path. This is intentional, not separate geometry.

`previous_contact` describes the immediately preceding **raw** contact set.
Repeated same-anchor raw episodes increment Path Step and update previous/last
anchors even though attention-transition alerts are suppressed. Alert history
therefore is not a complete list of raw path steps. A table with both last and
previous anchors equal to CURRENT MIDPOINT is legal after two separate raw
current-midpoint episodes. It cannot, however, account for the 101.49 versus
102.15 geometry contradiction within one run.

## Execution and alert timing

Actual top-to-bottom order for an anchor-transition bar:

1. Select canonical slot inputs, symbol guard, and activation availability.
2. Derive both rounded midpoints, Migration EQM, and existing visual geometry.
3. Run the separate EQM-zone interaction detector and its optional alerts.
4. Derive current-price region, adjacent anchors, and migration direction.
5. Initialize event-local defaults and compare the existing observer identity.
6. Clear unavailable state, or on a confirmed bar baseline a new context; else
   detect fresh anchor contacts using the candle's low/high.
7. Capture previous contact; copy previous reached anchor; promote last anchor;
   store timestamp; increment path/EQM counts; store the new contact summary.
8. Create optional observer labels from post-mutation state.
9. Build and fire anchor/second-EQM alerts from post-mutation canonical state.
10. Prune labels and render the last-bar table from that same state.

Anchor contacts and state mutation are gated by `barstate.isconfirmed`.
Anchor and second-EQM alerts use `alert.freq_once_per_bar_close`. Table rendering
uses `barstate.islast` and updates on realtime executions, including the closing
execution after mutations. Before close it intentionally shows the last committed
path/contact state alongside current-price-derived region/adjacent anchors.
Historical bars execute the observer logic but TradingView notifications only
trigger on realtime bars. `barstate.isnew` is not used in the script.

The independent EQM-zone detector uses `varip` and optional intrabar alerts, but
does not mutate observer anchors/path/contact counts. Rollback or intrabar timing
cannot turn a fixed active-slot midpoint of 102.15 into 101.49, nor make that
geometry's migration HIGHER. No `varip` changes were justified or made.

## Replay/debug checks

Added [`tests/test_trade_desk_observer_context.py`](../../tests/test_trade_desk_observer_context.py).
Run without new dependencies:

```sh
python3 -B tests/test_trade_desk_observer_context.py -v
```

Ten tests pass, covering the requested cases and additional boundaries:

- A/B: current below previous → LOWER; above → HIGHER; equal → COINCIDENT.
- C/D: CURRENT MID → EQM at step 23; EQM → PREV MID at step 24; payload and
  table agree, with canonical values 102.15 / 102.99 / 103.83.
- E/F: each current/previous bound and activation field resets/baselines correctly.
- G: active-slot swap resets state and reverses migration coherently.
- H: identical deterministic bars produce identical final state after a fresh
  historical replay; historical replay does not send notifications.
- I: a new timeframe run does not inherit incompatible state. Same synthetic
  bars agree; real timeframe aggregation can legitimately change counts.
- Wrong symbol, invalid current/previous bounds, and pre-activation clearing.
- No creation/reset-bar inferred contacts; contact continues without duplication;
  leave/re-entry creates a fresh contact.
- Intrabar anchor contact does not mutate the path; close renders updated state.
- Repeated raw EQM episodes retain existing path-count and second-EQM behavior.
- Two separate synthetic runs reproduce old-chart 101.49/HIGHER/step 6 versus
  alert-context 102.15/LOWER. These are constructed demonstration inputs, not
  recovered SOLUSDT chart inputs.
- Static checks verify single geometry definitions, existing identity fields,
  and mutation → alert → table ordering.

The bounded scalar replay translates the **actual** MRZ geometry, observer
reset/contact statements, helper functions, payload builders, emission guards,
and table expressions from the Pine source. It does not create a parallel
observer detector. The adapter supplies a 0.01 SOL tick, scalar Pine helpers,
and synthetic confirmed/realtime flags. It is not a Pine compiler, complete
rollback/cache emulator, actual TradingView alert test, or a replay of the
missing real SOLUSDT OHLC data. A live-context cause remains unconfirmed.

## Minimal correction and remaining reconciliation

State-flow before and after is unchanged:

```text
MRZ slot inputs → canonical geometry + existing identity
               → one observer state → alert payload + table
```

No second identity, counter, reset pathway, alert-specific geometry, or
table-specific state was introduced. The guard already covers compatible
context changes; blindly adding resets would change prospective contact
semantics without addressing TradingView's independently saved alert.

To resolve the live incident without guessing:

1. Preserve both raw alert payloads, bar timestamps, alert creation time,
   current table screenshot, and chart/alert symbol and timeframe.
2. Capture the chart indicator's source version, active slot, both bounds,
   both activation timestamps, and configured ticker. Check for duplicate
   TD_1.0 instances and which instance is the alert condition.
3. Compare the selected alert's saved configuration/source with that chart
   instance. Recompute rounded midpoints from those exact inputs.
4. If they differ, establish the intended authoritative chart configuration,
   then replace only the identified old alert from that corrected instance.
   Existing alerts cannot be updated by Pine code or a local source commit.
5. Compare the next alert with the table at its **same confirmed contact bar**.
   A later table can legitimately contain subsequent raw contacts and steps.

Do not delete or recreate alerts until their exact identity and intended context
are resolved. No alert was altered in this audit. If identical source, inputs,
symbol, timeframe, dataset, and observation bar still disagree, capture those
artifacts for a reproducible runtime investigation before changing semantics.

Only this audit and replay fixtures were added. MRZ geometry, anchor/contact
definitions, observer reset logic, event names/schema, evidence, route logic,
strategy absence, and EDGE backend are unchanged. Nothing was deployed.
