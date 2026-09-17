# Episode 002 — Pre-run skeleton

Use with [MANDATE.md](MANDATE.md), [SOP_SINGLE_SYMBOL.md](SOP_SINGLE_SYMBOL.md),
[EDGE_GLOSSARY.md](EDGE_GLOSSARY.md), and
[EPISODE_RECORD.md](EPISODE_RECORD.md).

This record is prospective and append-only. Complete factual fields only from
available sources, record each Astra decision before its subsequent outcome,
freeze every T0 entry, and keep later T1 review separate. No market decision has
been made in this skeleton.

## Episode 002 Objective

Episode 002 is the first clean prospective run of the current Trade Desk
operator/Astra workflow. This objective is frozen before mock validation and the
real run.

### Primary objective

Determine whether Astra adds useful discretionary trading judgment beyond the
deterministic EDGE / Trade Desk state when the operator selectively requests
attention using `[SYMBOL] WAKE`.

The operator determines when Astra attention is warranted but does not provide
the analytical reason for the wake.

Astra independently:

- restores the current Trade Desk lifecycle
- selects the chart context, timeframe, structural geometry, and evidence it
  considers relevant
- interprets the situation prospectively
- makes the appropriate Trade Desk decision
- preserves continuity across subsequent wakes

### Secondary objective

Preserve the objective state present at each wake so later Episode Run analysis
can investigate which observable situations were associated with useful Astra
assessments. This may include, without assigning significance in advance:

- EQM contact chronology
- anchor chronology
- MRZ structural state
- IPDA context
- price location
- evidence present or subsequently inspected by Astra

Episode 002 does not assume that any EQM contact number, touch point, evidence
type, or structural condition has trading significance.

### What Episode 002 is testing

1. Whether Astra independently identifies relevant evidence rather than merely
   repeating deterministic Trade Desk facts.
2. Whether Astra adds useful discretionary interpretation or decision value.
3. Whether Astra maintains prospective continuity across multiple WAKE calls.
4. Whether a clean factual wake record can later support discovery of better
   attention-selection rules.

### Success criteria

Episode 002 is a valid successful research run even if no trade occurs. The run
should produce:

- prospective frozen Astra decisions
- independent Astra evidence selection
- continuity across repeated wakes
- no operator analytical prompting
- no retrospective rewriting
- coherent trade management if an ENTER occurs
- sufficient factual wake-state data for later milestone review

### Out of scope

Episode 002 does not attempt to:

- prove that any specific EQM contact number is optimal
- optimize wake frequency
- automate Astra wake
- prove statistical trading edge
- redesign MRZ logic
- introduce a database
- introduce multi-symbol orchestration

## Frozen methodology

- **Episode Run:** 002
- **Episode Run Status:** [set ACTIVE when the prospective run begins]
- **SOP Version:** SINGLE-SYMBOL v0.2
- **Canonical Operator Command:** [SYMBOL] WAKE
- **Initial Astra Attention:** Operator-selected prospectively
- **Wake Routing:** Per SOP Wake Router
- **Operator Wake Reason:** Not supplied to Astra
- **Objective State at Wake:** Captured prospectively where applicable
- **Natural Completion Rule:** NEXT AUTHORITATIVE MRZ MIGRATION
- **Mode:** BLIND DISCOVERY
- **Discipline:** Prospective / append-only; T1 must not rewrite T0

## Pre-run identification

- **Symbol / venue:** [not yet selected]
- **Structural episode ID / migration reference:** [not yet supplied]
- **Start time / timezone:** [not yet started]
- **Evidence sources / as-of time:** [not yet supplied]
- **Timeframes selected at start:** [not yet selected]
- **Start context:** [not yet supplied]
- **Trade / position continuity:** [not yet supplied]

## Live model and allowance

- **Live Model:** [verify before start; mandate default is GPT-6 Astra]
- **Reasoning Effort:** [verify before start; mandate default is Medium]
- **Model Start Time:** [not yet started]
- **Model Interrupted:** [not yet applicable]
- **Handoff Model:** [not applicable unless recorded later]
- **Handoff Time:** [not applicable unless recorded later]
- **Model verification:** [pending]
- **Allowance check:** [pending]
- **Interruption risk accepted:** [not applicable or pending]
- **Live sample attribution:** [pending actual run]

## T0 — authoritative run initialization

- **Initialization timestamp / timezone:** [pending]
- **Authoritative source / as-of time:** [pending]
- **Current MRZ:** [pending]
- **Previous MRZ:** [pending]
- **Migration chronology / direction:** [pending factual state]
- **Route authority / structural location:** [pending]
- **Current MRZ midpoint:** [pending]
- **Migration EQM:** [pending]
- **Previous MRZ midpoint:** [pending]
- **TradeDesk.pine configuration reconciliation:** [pending]
- **Optional Second EQM Contact Alert / alert reference:** [not yet supplied; no wake requirement]
- **Initial deterministic observer context:** [pending]
- **Initial distinct EQM contact count:** [pending]
- **Position state:** [pending operator report]
- **Freeze:** [complete before later observations]

## TWAKE — first Astra assessment

- **Wake Timestamp / timezone:** [pending]
- **Wake Command:** [actual SYMBOL WAKE; no analytical suffix]
- **Wake Route:** [pending; per SOP lifecycle state]
- **Position State at Wake:** [pending operator report; FLAT / OPEN]
- **Chart timeframe at wake:** [pending]
- **Path Step at wake:** [pending]
- **Distinct EQM Contacts at Wake:** [pending deterministic value]
- **Current deterministic observer context:** [pending; include Last Reached Anchor, Previous Reached Anchor and Last Contact/contact chronology, or frozen source reference]
- **Current MRZ Migration:** [pending]
- **Current IPDA 20W Zone:** [pending]
- **Evidence / timeframes Astra actually inspected:** [pending Astra selection]

### First Astra decision — complete prospectively

- **Decision ID:** [002 + unique sequence]
- **Timestamp / timezone:** [pending]
- **Decision model / reasoning effort:** [pending actual author]
- **Prior decision / thesis link:** [none or reference]
- **Position context:** [pending operator report]
- **Decision:** [per Wake Route; FLAT: WAIT / ENTER / NO TRADE; OPEN: HOLD / REDUCE / EXIT]
- **Observed facts:** [pending]
- **Astra interpretation:** [pending]
- **Relevant evidence:** [pending]
- **Contradictory evidence:** [pending]
- **Reason for decision:** [pending]
- **What would change my view:** [pending]
- **Next Reassessment Conditions:** [pending prospective observable developments]
- **Thesis invalidation:** [pending or not applicable]
- **Confidence / uncertainty (optional):** [pending]
- **Freeze:** [complete before subsequent outcome]

#### ENTER contract — complete only if Decision = ENTER

- **Action:** ENTER
- **Position direction:** [pending]
- **Entry rationale:** [pending]
- **Initial invalidation:** [pending]
- **Management conditions / reassessment events:** [pending]
- **Current exit intent:** [pending]
- **Position State:** OPEN

#### Evidence inspected — optional factual metadata

- **Raw price / candles:** [YES / NO; timeframe or reference if useful]
- **Swing structure:** [YES / NO; timeframe or reference if useful]
- **Displacement:** [YES / NO]
- **FVG:** [YES / NO]
- **VI:** [YES / NO]
- **OB:** [YES / NO]
- **CE:** [YES / NO; evidence class if useful]
- **IPDA:** [YES / NO]
- **Other:** [description or none]

## Subsequent T0 decisions

Append each later decision using the complete T0 block in
[EPISODE_RECORD.md](EPISODE_RECORD.md). Freeze objective state for each
`[SYMBOL] WAKE` and apply the SOP Wake Router. Prior reassessment conditions are
guidance, not wake gates. Preserve the same trade lifecycle across HOLD, REDUCE,
and EXIT.

## Operator execution and trade performance

- **Execution record:** [append only if reported]
- **Executed-trade performance:** [append only for an actually executed trade]
- **Migration during an open trade:** [append if applicable]

Do not calculate hypothetical performance for WAIT or NO TRADE.

## T1 — outcome review

- **Review time / timezone:** [pending]
- **Reviewer model / reasoning effort:** [pending]
- **Decision IDs reviewed:** [pending]
- **Observation window / sources:** [pending]
- **Objective subsequent price path:** [pending]
- **Actual execution result:** [pending or none]
- **Decision quality:** [pending]
- **Lessons / open questions:** [pending]
- **Episode completion record:** [pending]

T1 may evaluate frozen T0 records but must not rewrite them.

## Episode Run milestone review

- **Initial wake utility:** [pending]
- **Structural insight beyond deterministic panel:** [pending]
- **Evidence-selection observations:** [pending]
- **Reassessment-condition quality:** [pending]
- **Operator friction:** [pending]
- **Lifecycle-continuity issues:** [pending]
- **Trade performance, if applicable:** [pending or not applicable]
- **SOP change candidate:** [pending or none]
- **Change justified now:** [YES / NO]
- **Reason:** [pending]
