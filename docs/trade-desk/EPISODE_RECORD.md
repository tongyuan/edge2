# Prospective episode record

Use with [MANDATE.md](MANDATE.md) and [EDGE_GLOSSARY.md](EDGE_GLOSSARY.md).
Copy the template below for each episode. Keep entries brief; cite only the
evidence considered. Use `unknown` or `not available` for missing facts.

Record each T0 decision before its subsequent outcome is known, then freeze
it. Append a new decision with its own ID for any changed view, management
recommendation, or extension thesis; link the earlier decision. Never
rewrite T0 during T1. Append dated corrections without removing the original.
Preserve WAIT, NO TRADE, mistakes, losses, and contradictory evidence.

Choose and record timeframes before observing their subsequent outcomes.
Log later timeframe additions prospectively with the next decision and a
reason; never select whichever historical view best explains the result.
Recommendations are distinct from operator execution. No recommendation
implies an order or fill, and no trade may be reconstructed retrospectively.

**STRUCTURAL EPISODE != TRADE.** A structural episode follows one authoritative
migration-defined MRZ structure. It may contain no trade, and a trade may receive
multiple management decisions or remain open into a later structural episode.
MRZ migration does not automatically close a position.

## Episode template

- **Episode ID:** [unique ID]
- **Structural episode ID / migration reference:** [authoritative structure]
- **Symbol:** [instrument / venue if needed]
- **Start time:** [timestamp with UTC offset and named timezone]
- **Timeframes selected at start:** [timeframes; no default preference]
- **Evidence sources / as-of time:** [EDGE state reference, chart capture or other workspace evidence; timestamp]
- **Start context:** [migration and active current + previous MRZ structure; missing state if any]
- **Trade / position continuity:** [no trade / new trade ID / open trade carried from prior episode, with source]

### Live model and allowance

The following defaults describe an ordinary Medium episode. Verify the actual
selection before use; replace defaults if different or unverified. Preserve
starting metadata and append later model events rather than overwriting it.

- **Live Model:** GPT-6 Astra
- **Reasoning Effort:** Medium
- **Model Start Time:** [timestamp with timezone]
- **Model Interrupted:** NO [YES / NO; once interrupted, retain YES]
- **Handoff Model:** [none, or replacement model and reasoning effort; link all handoffs]
- **Handoff Time:** [not applicable, or timestamp with timezone; link all handoffs]
- **Model verification:** [product information / operator confirmation and time, or unverified]
- **Allowance check:** [time, source, available allowance/reset information if shown, and operator assessment of whether completion appears feasible]
- **Interruption risk accepted:** [not needed, or explicit operator acceptance and timestamp if starting near unavailability; note uncertainty]
- **Live sample attribution:** [pure Medium / pure Ultra / mixed-model / other / unverified; track interruption separately]

No model or effort change merely to obtain a stronger live opinion. Follow the
[continuity policy](MANDATE.md#model-continuity-and-live-episode-policy).

### EDGE structural snapshot

Capture authoritative values as supplied. Reference an attached snapshot
instead of transcribing every field when it remains auditable. Flag suspected
data problems; do not replace EDGE levels with inferred chart levels.

| Field | Value or source reference |
| --- | --- |
| Current MRZ | [ID, bounds, midpoint, activation time] |
| Previous MRZ | [ID, bounds, midpoint, activation time] |
| Migration chronology / direction | [event reference and descriptive state] |
| Route authority / structural location | [WHO / WHERE and authoritative current–previous relationship] |
| Current MRZ midpoint | [authoritative value or source reference] |
| Migration EQM | [midpoint of Current and Previous MRZ midpoints, or unavailable] |
| Previous MRZ midpoint | [authoritative value or source reference] |
| Relevant TradeDesk.pine observations | [Price Region, anchor contacts/chronology, displayed evidence, lifecycle states, or capture reference as needed] |

These anchors are authoritative structural references. They do not define
Astra's discretionary trading dealing range.

### T0 — decision log

Repeat this block for every decision. Distinguish authoritative EDGE facts
and directly visible price observations from inferred price-action labels.

- **Decision ID:** [episode ID + unique sequence]
- **Timestamp / timezone:** [recorded before subsequent outcome]
- **Decision model / reasoning effort:** [actual author; reference the applicable model-start or handoff record]
- **Wake context:** [MRZ_ANCHOR_TRANSITION / MRZ_EQM_INTERACTION / MRZ_MIGRATED / OPERATOR_REVIEW / OTHER; context only, not the cause of the decision]
- **Prior decision / thesis link:** [ID or none; identify a new extension thesis explicitly]
- **Timeframes / evidence as of this decision:** [references; record additions and reason]
- **Structural snapshot update:** [new source / changed authoritative facts, or unchanged]
- **Position context:** [operator-reported position / no position / unknown; distinguish any recommendation awaiting execution]
- **Decision:** [WAIT / ENTER / HOLD / REDUCE / EXIT / NO TRADE]
- **Observed facts:** [authoritative EDGE state and visible price facts, with sources]
- **Astra interpretation:** [what price may be attempting; distinguish inference from fact]
- **Relevant evidence:** [what mattered; what seemed irrelevant or misleading if useful]
- **Contradictory evidence:** [evidence against the view, or none observed]
- **Reason for decision:** [why action or inaction is justified now]
- **What would change my view:** [new information or behavior to reassess]
- **Thesis invalidation:** [if applicable; otherwise not applicable]
- **Confidence / uncertainty (optional):** [limits of the view]

#### ENTER contract — required only when Decision = ENTER

Complete every field in the same prospective T0 entry. The values are
Astra-defined from current evidence; this template prescribes no stop distance,
risk/reward, target anchor, PD array, dealing range, or timeframe.

- **Action:** ENTER
- **Position direction:** [direction]
- **Entry rationale:** [current prospective rationale]
- **Initial invalidation:** [condition or event]
- **Management conditions / reassessment events:** [conditions or events]
- **Current exit intent:** [current intent]
- **Position State:** OPEN

#### Evidence inspected — optional factual metadata

Record only what Astra actually inspected. Omit the block or mark items `NO`
when not inspected. The list is not a checklist, score, hierarchy, or inspection
order, and `YES` carries no implied predictive value.

- **Raw price / candles:** [YES / NO; timeframe or reference if useful]
- **Swing structure:** [YES / NO; timeframe or reference if useful]
- **Displacement:** [YES / NO]
- **FVG:** [YES / NO]
- **VI:** [YES / NO]
- **OB:** [YES / NO]
- **CE:** [YES / NO; evidence class if useful]
- **IPDA:** [YES / NO]
- **Other:** [description or none]

#### Discretionary dealing range — optional Astra analysis

Use only if Astra independently adopts a dealing range for this decision. It is
derived from price swing structure, is not authoritative EDGE state, and is not
populated from MRZ midpoint anchors.

- **Used:** [YES / NO]
- **Swing high:** [value, observation precision and source]
- **Swing low:** [value, observation precision and source]
- **Timeframe:** [timeframe Astra used]
- **Rationale:** [why this swing structure was relevant]

### Model interruption / handoff log

Append this block only when needed. Freeze the last original-model decision;
mark **MODEL INTERRUPTED** and set Model Interrupted to YES. The operator logs
the event if model access is unavailable and remains responsible for any open
position. Logging the event does not authorize a replacement to trade.

- **Interruption time / recorded-at time:** [both timestamps with timezone; identify uncertain event time]
- **Episode status:** MODEL INTERRUPTED
- **original_model:** [model and reasoning effort]
- **last_original_model_decision:** [frozen decision ID and timestamp]
- **Active position state:** [operator-reported position / none / unknown, with source/time]
- **Current thesis / invalidation:** [last recorded thesis and invalidation; link T0]
- **reason_for_handoff:** [usage limit / availability / other constraint; record cause even if no handoff occurs]
- **Operator continuation choice:** [stop / await same-model access / explicit replacement authorization, with timestamp]
- **replacement_model:** [actual model and reasoning effort, or none]
- **handoff_timestamp:** [timestamp with timezone, or not applicable]
- **Resumption / intervening operator actions:** [time, actual resumed model/effort, and action references if applicable]
- **Sample attribution update:** [mixed-model if live model/effort changes; preserve interrupted status even if the same model resumes]

Keep all handoff records and attribute each later T0 decision to its actual
model and effort. Never represent replacement decisions as Medium decisions.
No Medium → Ultra → Medium mid-trade escalation during initial research.

### Operator execution record

Append only when execution information is available; link the relevant T0.

- **Decision ID / recorded-at time:** [reference and timestamp]
- **Execution status:** [operator-reported execution / explicitly no execution / unknown]
- **Actual action / fills:** [timestamp, direction, quantity, price and source if reported; otherwise not available]
- **Differences from recommendation:** [if any; never infer fills from the chart]

### Migration during an open trade

Append when an authoritative migration occurs while a position remains open.
Begin the linked structural episode without closing or rewriting the trade.

- **migration_during_trade:** YES
- **migration_event_time:** [authoritative timestamp]
- **pre_migration_position:** [operator-reported state and source]
- **post_migration_structure:** [linked new structural episode / snapshot]
- **post_migration_decision:** [new prospective T0 decision ID when Astra is invoked, or pending]
- **eventual_exit:** [later execution reference, or open]
- **trade_outcome:** [complete later in T1, or pending]

### T1 — outcome review

Complete later, separately from T0. Repeat or extend reviews with dated
entries as needed; every conclusion must point back to a frozen decision.
Ultra reviews are post-episode only during initial research and must not rewrite
Medium T0. Reviewer identity does not change the episode's live-model attribution.

- **Review time / timezone:** [timestamp]
- **Reviewer model / reasoning effort:** [actual reviewer, or operator; distinguish from live trader]
- **Episode completion / sample attribution:** [end/stop reference; live model/effort, pure or mixed, interrupted or uninterrupted, and inclusion/exclusion basis for performance comparisons]
- **Decision IDs reviewed:** [links to original T0 entries]
- **Observation window / sources:** [start, end and evidence available for this review]
- **Subsequent price path:** [objective sequence, including ambiguous or missing evidence]
- **Actual entry / exit result:** [linked execution record and measurable result, or no execution / unknown; WAIT and NO TRADE remain valid records]
- **MFE / MAE (optional):** [only if measurable; specify direction, reference price, window, units and data source; label any non-executed reference measurement explicitly]
- **Thesis validity / changed view:** [what happened; link each prospectively recorded change to its T0 ID; identify hindsight-only observations as such]
- **Decision quality:** [assess reasoning using information available at T0, separately from the result]
- **Mistakes / misunderstandings:** [preserve errors and contrary evidence]
- **Lessons / open questions:** [what was learned and what remains uncertain]
- **Possible hypothesis generated (optional):** [new hypothesis ID in HYPOTHESIS_LOG.md, or none]
- **Episode end / stop time (if complete):** [timestamp and operator stop or other end context]

Never write “I would have entered here” after seeing the completed move.
A favorable outcome cannot retroactively supply a missing decision or turn
ambiguous T0 evidence into a confirmed signal.
