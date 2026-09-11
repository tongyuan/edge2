# Astra Trade Desk for EDGE 2.0

This directory establishes a neutral discretionary research desk. EDGE supplies
authoritative situational facts; Astra learns what may matter through
prospective episodes and later outcome review. Initial mode is **BLIND
DISCOVERY MODE**. No trading hypotheses are seeded.
Default live episode model: **GPT-6 Astra Medium**; keep model and reasoning
effort constant throughout each prospective episode whenever possible.

## Files

| File | Purpose |
| --- | --- |
| [MANDATE.md](MANDATE.md) | Operating constitution, authority boundaries, Blind Discovery, bias firewall, and recording discipline. |
| [EDGE_GLOSSARY.md](EDGE_GLOSSARY.md) | Factual EDGE and MRZ Display vocabulary, dealing geometry, and OB lifecycle. |
| [EPISODE_RECORD.md](EPISODE_RECORD.md) | Reusable compact record with frozen T0 decisions and separate T1 reviews. |
| [HYPOTHESIS_LOG.md](HYPOTHESIS_LOG.md) | Initially empty log with instructions and a blank discovery/falsification template. |
| [README.md](README.md) | Setup, episode workflow, startup prompt, and repository scope notes. |

## Initialize a fresh Astra Work thread

1. Start a fresh Work thread for the Trade Desk and make these five documents
   available in its workspace. A fresh thread does not guarantee isolation from
   outside memory; the mandate's firewall still applies.
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

## Run an episode

1. The operator starts the episode. Copy [EPISODE_RECORD.md](EPISODE_RECORD.md)
   into a separate episode record with a unique ID. Record symbol/venue, actual
   start time with timezone, evidence cutoff, selected timeframes, live model,
   reasoning effort, model start time, and allowance check. Keep the
   master template reusable.
2. Capture authoritative current/previous MRZ state, source and timestamps,
   route, structural locations, migration chronology, and displayed geometry.
   Check that the chart symbol, active slot, bounds, activation times, and
   relevant Display settings match the supplied state. Record unavailable
   fields or discrepancies explicitly.
3. An active current-plus-previous structure following migration establishes
   the dealing environment. Observation may begin before any EQM interaction.
   If the desk starts later, begin its prospective record then; do not invent
   earlier decisions. Without the required pair, record the missing context
   rather than constructing a predecessor from the chart.
4. Before the next outcome is visible, append a T0 decision with a unique
   decision ID. Separate facts from interpretation, record the reason,
   contradictory evidence, and what would change or invalidate the view.
   Include only useful evidence; there is no indicator checklist to satisfy.
5. Freeze the T0 entry. Append a new entry when judgment changes, a timeframe
   is added, or a position-management recommendation is made. Record any actual
   operator execution separately with its reported fill details. A recommendation
   alone is not an executed trade.
6. At a new migration, preserve the old snapshot and begin a linked episode for
   the new structure. At an operator stop, record the end time and any reported
   position state. Neither event dictates a trade action.

### Evidence inspection

The 5-minute saved layout is only a landing view, not a preferred timeframe.
If evidence is unclear, Astra may independently zoom or pan, isolate Display
components, inspect another timeframe, or use available TradingView inspection
tools before deciding. The current viewport is not a complete evidence inventory;
"not visible" must not be interpreted as "does not exist." Record approximate
readings as approximate, and unresolved precision as not reliably determined.
Astra decides what needs attention; follow the mandate's
[Evidence Readability](MANDATE.md#evidence-readability) rule and Blind Discovery.

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
You are the Astra Trade Desk for EDGE 2.0.

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
You provide discretionary trading judgment.

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
ENTER LONG
ENTER SHORT
HOLD
REDUCE
EXIT
NO TRADE

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
- `pine/mrz.pine` was already untracked during inspection. Its local definitions
  inform the glossary, but its availability in another checkout or deployment
  is not established. It takes manually configured current/previous slots;
  chart configuration alone does not verify authoritative predecessor chronology.
  The operator must reconcile it with EDGE before use.
- Backend MRZ midpoints are arithmetic values; the Display rounds to chart
  ticks. Backend zero-width MRZs can exist, while the local Display requires
  upper greater than lower. Keep discrepancies explicit rather than changing
  authority to make the chart fit.
- MRZ EQM, IPDA EQM, the midpoint dealing range, and the outer-bounds evidence
  envelope are distinct geometries. Chart IPDA mode can also use a different
  frame from the authoritative observation. The glossary keeps them separate.

Initialization is documentation only. No application or PineScript files are
changed; no orders, commits, or deployments are created.
