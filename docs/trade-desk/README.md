# EDGE Trade Desk

This directory defines the persistent, operator-controlled EDGE trading
workspace. EDGE supplies authoritative structure, TradingView and
TradeDesk.pine provide deterministic observation and available evidence, Astra
serves as the invoked discretionary decision adviser, and the operator currently
orchestrates synchronization, wake, and securities execution. The workspace
retains state whether Astra is active or unavailable.

Initial mode is **BLIND DISCOVERY MODE**. No trading hypotheses are seeded.
Default live episode model: **GPT-6 Astra Medium**; keep model and reasoning
effort constant throughout each prospective episode whenever possible.

## Files

| File | Purpose |
| --- | --- |
| [MANDATE.md](MANDATE.md) | Operating constitution, authority boundaries, Blind Discovery, bias firewall, and recording discipline. |
| [EDGE_GLOSSARY.md](EDGE_GLOSSARY.md) | Factual EDGE and TradeDesk.pine vocabulary, structural geometry, observer events, and evidence lifecycle. |
| [EPISODE_RECORD.md](EPISODE_RECORD.md) | Reusable compact record with frozen T0 decisions and separate T1 reviews. |
| [HYPOTHESIS_LOG.md](HYPOTHESIS_LOG.md) | Initially empty log with instructions and a blank discovery/falsification template. |
| [README.md](README.md) | Setup, episode workflow, startup prompt, and repository scope notes. |

## Initialize a fresh Astra Work thread

1. Start a fresh Work thread for Astra as the Trade Desk's discretionary adviser
   and make these five documents available in the persistent workspace. A fresh
   thread does not guarantee isolation from outside memory; the mandate's
   firewall still applies.
2. Provide authoritative EDGE state and chart access or timestamped captures as
   available. Do not load prior strategy discussions, preferred setups, trading
   conclusions, or operator hypotheses as starting knowledge.
3. Paste the startup prompt below. Astra should read the mandate and glossary,
   confirm the boundaries, and wait for the first prospective episode without
   formulating trading hypotheses. If the documents or evidence are unavailable,
   it must identify the gap instead of claiming access.

## Live-model preparation and continuity

Before each live episode, the operator verifies GPT-6 Astra with Medium effort
and checks whether the available allowance appears sufficient to reasonably
complete it. Record the check in the episode template. Do not start near model
unavailability without explicit operator acceptance of interruption risk.
Unknown allowance is recorded as unknown; no fixed token budget or guaranteed
episode duration is assumed. Use the product's current usage information;
[official usage documentation](https://learn.chatgpt.com/docs/pricing) provides
background, not an account-specific allowance check. These documents do not
select a model or enforce availability automatically.

Follow the [mandate's model policy](MANDATE.md#model-continuity-and-live-episode-policy)
if access is interrupted: preserve the last decision, timestamp, position,
thesis, and invalidation; mark **MODEL INTERRUPTED**. The operator manages any
open position. A replacement requires explicit operator choice and a recorded
handoff; subsequent decisions carry the replacement's identity, and the episode
is marked mixed-model. Changing effort also counts as a handoff.

Use Ultra for review of completed episodes during initial research, with a
separate reviewer attribution. Do not escalate Medium → Ultra → Medium live.
Later live Ultra testing uses complete Ultra-owned episodes after sufficient
clean Medium evidence exists. Keep mixed and interrupted results distinguishable;
do not assume more reasoning improves trading. Reserve models may help maintain
files and records while preserving authorship, but cannot silently take over
live judgment.

## Current operating workflow

```text
EDGE migration
  → operator synchronization where required
  → TradeDesk.pine deterministic observation
  → local TradingView attention alert
  → neutral operator invocation of Astra
  → WAIT / ENTER / HOLD / REDUCE / EXIT / NO TRADE
  → operator securities execution where applicable
```

The current research workflow uses manual operator synchronization and Astra
wake. Astra is not expected to poll or monitor TradingView continuously, and a
native automatic Astra wake is not assumed. Gmail, Slack, or another external
trigger is not documented as a production wake mechanism. Attention events
request possible reassessment; they do not cause a trade decision.

## Run an episode

1. The operator starts the episode. Copy [EPISODE_RECORD.md](EPISODE_RECORD.md)
   into a separate episode record with a unique ID. Record symbol/venue, actual
   start time with timezone, evidence cutoff, selected timeframes, live model,
   reasoning effort, model start time, and allowance check. Keep the
   master template reusable.
2. Capture authoritative current/previous MRZ state, source and timestamps,
   route, structural locations, migration chronology, and displayed geometry.
   Check that the TradeDesk.pine chart symbol, active slot, bounds, activation
   times, and relevant presentation settings match the supplied state. Record
   unavailable fields or discrepancies explicitly.
3. An active current-plus-previous structure following migration establishes
   the structural environment. Observation may begin before any EQM interaction.
   If the desk starts later, begin its prospective record then; do not invent
   earlier decisions. Without the required pair, record the missing context
   rather than constructing a predecessor from the chart.
4. Before the next outcome is visible, append a T0 decision with a unique
   decision ID. Separate facts from interpretation, record the reason,
   contradictory evidence, and what would change or invalidate the view.
   Include only useful evidence; there is no indicator checklist to satisfy.
5. Freeze the T0 entry. ENTER requires direction, rationale, initial
   invalidation, management/reassessment conditions, current exit intent, and
   `Position State = OPEN`. Append a new entry when judgment changes, a
   timeframe is added, or a position-management recommendation is made. Record
   actual operator execution separately; a recommendation alone is not a fill.
6. At a new migration, preserve the old snapshot and begin a linked episode for
   the new structure. Preserve any open trade unless the operator reports an
   execution change; migration is not an automatic exit. At an operator stop,
   record the end time and reported position state. Neither event dictates a
   trade action.

A structural episode is tied to one authoritative migration-defined structure;
it is not the same thing as a trade. An episode may contain no trade, while one
trade may receive multiple management decisions and continue into the next
structural episode.

### Evidence inspection

The saved structural chart is a neutral landing view; its saved timeframe is
presentation, not a preferred analytical timeframe. Proximal evidence layers
may be visually off by default. Detection and lifecycle remain independent of
visibility, so "not visible" must not be interpreted as "does not exist."

If evidence is unclear, Astra may independently zoom or pan, inspect another
timeframe, selectively expose or hide evidence and CE layers, isolate evidence,
or return to a cleaner chart. Visibility choice is not a trading signal, and no
evidence layer or inspection order is preferred. Record approximate readings as
approximate and unresolved precision as not reliably determined. Follow the
mandate's [Evidence Readability](MANDATE.md#evidence-readability) rule and Blind
Discovery.

## Review and learn

Complete T1 later using the original decision ID, an explicit review time, and
an outcome observation window. Record the objective price path and actual
execution result where available. MFE/MAE are optional and require known
reference prices and measurement windows. WAIT and NO TRADE remain reviewable
without inventing fills or retrospective entries.

Review what Astra understood, misunderstood, changed prospectively, and learned.
T1 never edits T0. A late record is a recording gap, not a prospective decision.
Corrections are dated addenda; original facts and reasoning remain readable.
Record the reviewer model/effort independently of the live model. An Ultra
review after completion does not turn a Medium-owned episode into a mixed-model
live episode. Keep live handoffs and interruptions visible in performance samples.

If prospective observations generate a hypothesis, add a blank-template copy
to [HYPOTHESIS_LOG.md](HYPOTHESIS_LOG.md) with episode references, contradictions,
sample count, confidence, questions, and falsification criteria. Retain rejected
hypotheses. No outcome, pattern label, timeframe, or anchor has a predetermined
trading interpretation.

## Blind Discovery protection

> The presence of an EDGE variable does not imply predictive significance.
> Treat its trading value as unknown until supported by prospective
> observation and outcomes.

The mandate separates EDGE facts from Astra interpretation and excludes
operator beliefs from initialization. Visible outside beliefs are labeled
**OPERATOR PRIOR**; leading suggestions are **OPERATOR HYPOTHESIS**, not evidence.
Only independent prospective rediscovery may inform Trade Desk methodology.
Frozen decisions, contradiction tracking, and falsification preserve evidence
against emerging beliefs. This is a protocol enforced by Astra and operator
audit, not technical memory isolation or immutable file storage.

## Initial Astra startup prompt

Copy the following prompt into the fresh thread:

```text
You are Astra, the invoked discretionary decision adviser to the EDGE Trade
Desk. The Trade Desk is the persistent operator-controlled workspace; it is not
you.

Read and follow the Trade Desk Mandate and EDGE Glossary available in this
workspace.

Begin in BLIND DISCOVERY MODE.

The default live episode model is GPT-6 Astra with Medium reasoning effort.
Verify and record the actual live model, reasoning effort, model start time,
and the operator's allowance check before beginning. Do not claim a model
identity merely because this prompt names it.

Keep the live model and effort unchanged through the episode whenever possible.
Do not switch mid-trade for a stronger opinion. If access is interrupted,
freeze the last decision, record its timestamp, position state, thesis and
invalidation, and mark MODEL INTERRUPTED. The operator remains responsible
for open positions. Any replacement requires explicit operator choice,
recorded handoff details, replacement-model decision attribution, and a
mixed-model label for the episode.

During initial research, use Astra Ultra for post-episode review of completed
records, never as a Medium → Ultra → Medium live escalation. Do not rewrite T0.
Treat usage as an operational constraint, not market evidence, and do not
alter trading judgment to conserve tokens.

EDGE provides authoritative situational facts.
TradeDesk.pine provides deterministic structural observation and available
chart evidence.
You provide discretionary trading judgment when the operator invokes you.
The operator currently provides orchestration and securities execution.

Do not assume that any EDGE variable has predictive value merely because
it is shown to you.

For trading judgment and hypothesis formation, do not use operator trading
beliefs, prior hypotheses, remembered conclusions, or inferred preferences
from conversations outside this Trade Desk workspace.

Determine independently:

- what information matters
- what information does not
- what market behavior deserves attention
- when to wait
- when to enter
- when to hold
- when to reduce
- when to exit
- when no trade is justified

Record every trading decision before subsequent market outcomes are known.

Preserve mistakes, contradictory evidence, no-trade decisions and rejected
hypotheses.

Never redefine authoritative EDGE state.

Your available decisions are:

WAIT
ENTER
HOLD
REDUCE
EXIT
NO TRADE

If you decide ENTER, simultaneously record position direction, entry rationale,
initial invalidation, management or reassessment conditions, current exit
intent, and Position State = OPEN.

Confirm that you understand the mandate and are ready for the first
prospective EDGE trading episode.

Do not formulate trading hypotheses yet.
```

## Repository scope notes

Inspection at initialization found the following limitations:

- The repository documents production WHO + WHERE. WHEN and WHAT here name
  the requested Trade Desk research frame; this package adds no backend episode
  model, EQM workflow, automatic MFE/MAE calculation, or chart connection.
  Existing backend research episodes cover individual MRZ generations, including
  initial activation; they are distinct from these prospective two-MRZ records.
- [Architecture's cross-route note](../architecture.md#cross-route-boundary)
  describes a future no-op, while the current repository README and state engine
  support route-changing external migration. The glossary follows the current
  implementation and authoritative supplied state. The older file is unchanged.
  The root README's legacy exclusion list also mentions manual activation and
  chronology despite its current promotion and migration-history descriptions;
  that list is not used to define Trade Desk authority.
- `pine/TradeDesk.pine` is the current local TradingView Trade Desk observer and
  evidence-display source. It takes manually configured current/previous slots;
  chart configuration alone does not verify authoritative predecessor chronology.
  The operator must reconcile it with EDGE before use. `pine/mrz.pine`, if
  retained, is historical/reference code rather than the canonical observer.
- Backend MRZ midpoints are arithmetic values; the Display rounds to chart
  ticks. Backend zero-width MRZs can exist, while the local Display requires
  upper greater than lower. Keep discrepancies explicit rather than changing
  authority to make the chart fit.
- MRZ EQM, IPDA EQM, the MRZ midpoint span, and the outer-bounds evidence
  envelope are distinct geometries. The midpoint span is structural reference
  geometry, not Astra's discretionary trading dealing range. Where Astra uses a
  dealing range, it derives it from relevant price swings without a prescribed
  timeframe. Chart IPDA mode can also use a different frame from the
  authoritative observation.

Initialization is documentation only. No application or PineScript files are
changed; no orders, commits, or deployments are created.
