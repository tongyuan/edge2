# Single-Symbol Trade Desk SOP — v0.2

Use with [MANDATE.md](MANDATE.md), which remains authoritative. This SOP governs
one symbol at a time through sequential Episode Runs in Blind Discovery mode.
The operator synchronizes state, receives local attention alerts, wakes Astra
manually, and handles execution. This version adds no queue, multi-symbol
coordination, automated Astra wake, polling, or continuous Astra monitoring.

## Test Mode

An invocation explicitly marked `MOCK TEST` or `TEST MODE` exercises the normal
production Wake Router and the corresponding INITIAL_ASSESSMENT,
SUBSEQUENT_REASSESSMENT, or POSITION_MANAGEMENT procedure. Clearly label every
response `MOCK TEST — NOT RECORDED`. Use only the supplied synthetic lifecycle
state for routing; select analytical context and evidence independently as in
production.

For that invocation only, these test instructions override production-state
restoration and recording, without changing production routing. Do not create,
modify, append to, advance, or close any production Episode Run, including
`EPISODE_002.md`. Do not persist mock Astra decisions, position state,
reassessment conditions, trades, or wake events.

Discard the synthetic state after each mock case. Do not use one mock as
lifecycle history for another unless continuity is explicitly included in the
supplied synthetic fixture.

## Wake Router

Canonical operator command: `[SYMBOL] WAKE` (for example, `ZECUSDT WAKE`).
A deliberate WAKE means only that the operator considers this symbol worthy of
Astra attention now. Do not supply, ask for, or infer the operator's reason,
preferred evidence, touch point, direction, interpretation, or timeframe.

Restore the authoritative lifecycle state, then route:

- OPEN position → **POSITION_MANAGEMENT**
- FLAT + no prior Astra assessment in the current episode → **INITIAL_ASSESSMENT**
- FLAT + prior Astra assessment in the current episode → **SUBSEQUENT_REASSESSMENT**

The operator determines when attention is warranted, not which procedure runs.
The SOP determines procedure only; it does not judge the operator's reason for
attention. Astra independently determines the analysis. This router is Markdown
operating behavior, not a backend or automated invocation mechanism.

## Initial Assessment

For FLAT with no prior Astra assessment in the current episode, any deliberate
`[SYMBOL] WAKE` starts INITIAL_ASSESSMENT. There is no minimum EQM contact count
and no early, on-time, or late classification. The operator may wake at contact
#1, #2, #3+, another touch point, or any other observation, or keep observing.
No count or touch point has routing privilege or assigned trading meaning.

`MRZ_SECOND_EQM_CONTACT` reports only that the second distinct Migration EQM
contact occurred in the current observer structure. The operator may respond or
ignore it. The alert neither requires a WAKE nor controls routing.

While FLAT, Astra independently identifies relevant swing structure from actual
price swing highs and swing lows, using the timeframe and hierarchy it considers
useful. It assesses whether the structure is sufficiently coherent to support a
probable trade setup; whether it is still forming or sufficiently developed;
whether meaningful displacement occurred within or away from it; whether
current interaction supports a directional thesis and defensible invalidation;
and whether enough structure exists for a management plan. If the structure is
immature or ambiguous, WAIT is valid.

An EQM alert or WAKE remains attention only. Astra determines whether surrounding
swing structure is still forming, sufficiently developed for a trade, developed
but not currently actionable, or irrelevant. No contact count, violent move, or
EQM-plus-swing sequence establishes a canonical setup.

Astra returns WAIT, ENTER, or NO TRADE and prospectively records the inspected
context and evidence, interpretation, rationale, and reassessment conditions.

## Astra controls evidence inspection

The operator determines when Astra is invoked. Once invoked, Astra controls the
analytical view. At TWAKE, Astra begins from the normal Trade Desk state and
should notice and consider the deterministic context already available: MRZ
Migration, IPDA 20W Zone, Price Region, Upper Anchor, Lower Anchor, Last Reached
Anchor, Previous Reached Anchor, Path Step, Distinct EQM Contacts, and Last
Contact/contact chronology.
These are factual structural observations. Astra decides whether each is
relevant to its trading decision. IPDA 20W Zone is part of the current
environment, but no IPDA bucket has assigned directional or trading meaning.

Astra may choose timeframe, zoom, pan, the amount of left-side historical
context, raw candles, and swing structure. It may independently enable,
inspect, ignore, or disable `Show Current MRZ 1W / 2W` and
`Show Previous MRZ 1W / 2W`. These optional projections are structural reference
geometry only; their visibility assigns no support, resistance, target,
invalidation, continuation, reversal, or preferred direction. Neither
projection requires inspection.

Astra chooses the relevant swing timeframe and hierarchy, including 1m, 5m,
15m, 1h, or another available timeframe. No timeframe or swing pattern is
mandatory. Swing structure comes from actual price behavior; Current MRZ
midpoint, Migration EQM, and Previous MRZ midpoint remain reference geometry,
not a price-defined dealing range.

Astra also independently chooses whether to show and inspect Displacement, FVG,
VI, OB, or CE. It may inspect one class, several, all, or none. No proximal
evidence type is mandatory or ranked. Proximal evidence may remain hidden.

At TWAKE, the operator must not preselect optional geometry or evidence because
of an expected trade outcome. Astra decides what additional visual information
is useful. These display and inspection choices do not alter authoritative EDGE
state or prior frozen decisions. Blind Discovery prescribes no timeframe,
evidence type, geometry, confluence threshold, or inspection order.

The operator's reason for requesting attention is not analytical input and must
not constrain Astra's evidence selection or be inferred from visible evidence.

## Subsequent Reassessment

For FLAT with a prior Astra assessment in the current episode, any deliberate
`[SYMBOL] WAKE` starts SUBSEQUENT_REASSESSMENT. Restore the prior prospective
assessment; Astra independently determines what has materially changed.
Next Reassessment Conditions remain useful operator guidance, not permission
gates. They need not have occurred for the operator to request attention.
Apply the same FLAT swing-structure assessment to the current price state,
restoring earlier prospective observations without treating them as fixed truth.

## Position Management

For OPEN, `[SYMBOL] WAKE` starts POSITION_MANAGEMENT. Restore the recorded trade
lifecycle: original ENTER, thesis, entry, initial invalidation, management
conditions, prior HOLD/REDUCE decisions, latest reassessment conditions,
`migration_during_trade`, and current authoritative structure. Expected
management decisions remain HOLD, REDUCE, and EXIT.

Refresh relevant swing structure and assess actual price behavior around swing
highs and lows. Astra may consider them as structural, liquidity/sweep,
acceptance/rejection, reassessment, partial- or full-exit, or invalidation
references where useful. An approach, sweep, rejection, acceptance, failure to
continue, displacement through a level, or earlier structural failure requires
interpretation; none mechanically forces HOLD, REDUCE, or EXIT.

Restore any swing structure recorded at ENTER and determine whether it remains
relevant. If a newer hierarchy supersedes it, record the new structure and
reason prospectively without rewriting the entry-time T0 observation.

If Astra decides ENTER, the same prospective decision must provide:

- direction
- entry rationale
- initial invalidation
- management conditions
- reassessment conditions
- current exit intent
- `Position State = OPEN`

When swing structure supports entry, use the existing evidence and rationale
record to preserve the relevant swing high, swing low, timeframe or hierarchy,
and why it mattered where sufficiently defined. Do not invent exact swing levels
when the structure is ambiguous.

Subsequent Astra wakes manage the same trade lifecycle through HOLD, REDUCE, or
EXIT decisions. MRZ migration supplies new structural information; it is not an
automatic exit.

## Episode completion

Natural structural Episode Run completion is:

**NEXT AUTHORITATIVE MRZ MIGRATION**

A trade may never occur, may open and close inside the Episode Run, or may remain
open when the structural Episode Run ends. Episode is distinct from trade.

With FLAT or OPEN, an authoritative migration completes the old structural
episode and begins the next; the observer resets according to existing
semantics. With OPEN, preserve the trade as OPEN and record
`migration_during_trade`; a later WAKE routes to POSITION_MANAGEMENT. With FLAT,
the next WAKE routes according to assessments in the new episode. The operator
decides when to wake Astra; migration imposes no EQM-count requirement.

An interrupted run may instead be administratively closed as
`CLOSED-INCOMPLETE`. Interruption is not natural structural completion.

## Episode milestone review

After every Episode Run, review:

1. Was the operator-selected attention moment useful?
2. Did Astra derive useful information from T0 to TWAKE beyond repeating the
   deterministic Trade Desk panel?
3. Which evidence and timeframes did Astra independently inspect?
4. Did Astra produce useful prospective reassessment conditions?
5. Was operator lifecycle continuity clear?
6. What operator friction occurred?
7. Is that friction repeated or material enough to justify an SOP change?
8. If there was an executed trade, how did Astra perform?

Do not change the SOP merely because of one inconvenient observation. Episode
Runs are milestone tests of Astra and the operator procedure.

Distinct EQM contact count and objective wake snapshots are prospective research
data, not wake eligibility or confidence. Any useful contact-count or
evidence-selection relationship must be discovered later, not assumed here.
