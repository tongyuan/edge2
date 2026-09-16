# Single-Symbol Trade Desk SOP — v0.1

Use with [MANDATE.md](MANDATE.md), which remains authoritative. This SOP governs
one symbol at a time through sequential Episode Runs in Blind Discovery mode.
The operator synchronizes state, receives local attention alerts, wakes Astra
manually, and handles execution. This version adds no queue, multi-symbol
coordination, automated Astra wake, polling, or continuous Astra monitoring.

## SOP 1 — Initial Astra wake

For Episode 002, the initial Astra wake condition is:

**SECOND DISTINCT MIGRATION EQM CONTACT**

This is a structural maturity and attention condition only. It does not mean
resistance, support, rejection, continuation, reversal, bearish, bullish, long,
short, confirmation, or entry.

A distinct contact follows this chronology:

```text
Migration EQM contact
  → price leaves EQM contact
  → price later returns and contacts Migration EQM again
```

Consecutive bars that continuously intersect Migration EQM without leaving are
one distinct contact episode.

- First distinct EQM contact: **OBSERVE ONLY**
- Second distinct EQM contact: **INITIAL ASTRA WAKE**

Before relying on this condition, the operator reconciles the active
current/previous MRZ structure and enables `Enable Second EQM Contact Alert` in
the applicable TradingView alert configuration. The alert requests manual
operator attention; it does not wake Astra automatically.

## SOP 2 — Initial wake instruction

The operator uses this neutral instruction without adding directional
interpretation:

> [SYMBOL] generated a new Trade Desk attention event. Refresh the current EDGE
> and TradingView state. Inspect sufficient historical price and structural
> context to understand the present situation prospectively, using whatever
> timeframe, zoom, and available evidence you consider relevant. Then make the
> next Trade Desk decision under the mandate.

## SOP 3 — Astra controls evidence inspection

The operator determines when Astra is invoked. Once invoked, Astra controls the
analytical view. At TWAKE, Astra begins from the normal Trade Desk state and
should notice and consider the deterministic context already available: MRZ
Migration, IPDA 20W Zone, Price Region, Upper Anchor, Lower Anchor, Last Reached
Anchor, Previous Reached Anchor, Path Step, and Last Contact/contact chronology.
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

Astra also independently chooses whether to show and inspect Displacement, FVG,
VI, OB, or CE. It may inspect one class, several, all, or none. No proximal
evidence type is mandatory or ranked. Proximal evidence may remain hidden.

At TWAKE, the operator must not preselect optional geometry or evidence because
of an expected trade outcome. Astra decides what additional visual information
is useful. These display and inspection choices do not alter authoritative EDGE
state or prior frozen decisions. Blind Discovery prescribes no timeframe,
evidence type, geometry, confluence threshold, or inspection order.

## SOP 4 — First Astra assessment

For a flat symbol, Astra returns one of:

```text
WAIT
ENTER
NO TRADE
```

Astra also records:

- the structure and context inspected
- the evidence and timeframes inspected
- its current interpretation
- why the decision is justified
- observable developments that would warrant reassessment

## SOP 5 — Subsequent wakes

The second distinct EQM contact governs the initial Astra wake only. After the
first assessment, a third, fourth, or later EQM contact and the arbitrary passage
of time do not automatically wake Astra.

Astra must state prospective reassessment conditions. Continue deterministic
observation until one of those previously stated conditions occurs or a material
authoritative structural change occurs. The next wake must cite that condition
or event. The operator must not invent an intervening discretionary wake
condition.

## SOP 6 — Position lifecycle

If Astra decides ENTER, the same prospective decision must provide:

- direction
- entry rationale
- initial invalidation
- management conditions
- reassessment conditions
- current exit intent
- `Position State = OPEN`

Subsequent Astra wakes manage the same trade lifecycle through HOLD, REDUCE, or
EXIT decisions. MRZ migration supplies new structural information; it is not an
automatic exit.

## SOP 7 — Episode completion

Natural structural Episode Run completion is:

**NEXT AUTHORITATIVE MRZ MIGRATION**

A trade may never occur, may open and close inside the Episode Run, or may remain
open when the structural Episode Run ends. Episode is distinct from trade.

An interrupted run may instead be administratively closed as
`CLOSED-INCOMPLETE`. Interruption is not natural structural completion.

## SOP 8 — Episode milestone review

After every Episode Run, review:

1. Was the initial second-EQM-contact wake useful?
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
