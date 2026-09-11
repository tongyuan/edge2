# EDGE Glossary

Factual vocabulary for Blind Discovery. Definitions describe what exists;
they assign no predictive significance. Pattern labels such as bullish and
bearish identify the Display's orientation, not a trade recommendation.

## Situational frame

| Term | Factual meaning |
| --- | --- |
| WHO | The route owning the active authoritative MRZ, shown as SOURCE: `BTD` or `STR`. |
| WHERE | Structural location. MRZ LOCATION places the frozen MRZ midpoint in its activation IPDA frame; CURRENT LOCATION places the latest accepted observation price in that observation's IPDA frame. The latter is not a continuously updated market quote. |
| WHEN | For this Trade Desk, the active two-MRZ environment established by migration, plus the times of observations and attention events within it. This is an episode convention, not a new backend qualification or timing signal. |
| WHAT | The available raw candles, MRZ Display geometry, and Display-identified evidence, plus separately labeled visual observations by Astra. This is a descriptive category, not an authoritative prediction field. |
| Route authority | The singular owner stored as `active_mrz.route_owner`. `BTD` observations use the schema label `reclaim`; `STR` observations use `rejection`. These are route/type identifiers. |
| IPDA frame | The high/low range supplied with an authoritative observation. Its midpoint divides discount and premium; quarter levels subdivide shallow/deep locations. Exact IPDA midpoint has no route/location bucket. Below/above-range states are possible for the latest observation. |

MRZ location uses the activation frame and stays with that MRZ. CURRENT LOCATION
uses its own observation's frame. A chart IPDA overlay depends on its configured
mode and is not a substitute for either authoritative recorded frame.

## MRZ authority and chronology

| Term | Factual meaning |
| --- | --- |
| Current MRZ | The current authoritative core MRZ for the symbol, with its frozen bounds, midpoint, route, activation metadata, and structural location. |
| Previous MRZ | The immediate authoritative predecessor displaced by the migration that established the current MRZ. It is not a chart-selected older range. It may be unavailable before the first migration. |
| MRZ bounds | The persisted lower and upper prices defining the core MRZ. Later supporting observations do not resize these bounds. |
| MRZ midpoint | Arithmetic midpoint of the core bounds: `(upper + lower) / 2`. MRZ Display plots a tick-rounded midpoint; preserve the source distinction when recording values. |
| Activation | The recorded establishment time of an authoritative MRZ. Initial authority has an `MRZ_ACTIVATED` event; a successor has its own activation time through `MRZ_MIGRATED`. Formation start, delivery time, and chart viewing time are distinct. |
| Activation source | Persisted provenance such as `PRODUCTION_QUALIFIED` or `OPERATOR_PROMOTED`. Lifecycle provenance can persist through migration; it does not replace the successor's timestamp. |
| Migration | EDGE's authoritative replacement of the active MRZ by a qualified external successor, retaining old/new transition state. The displaced MRZ becomes previous. |
| Migration direction | Higher/lower movement of the current midpoint relative to its predecessor. It describes a structural change. **Predictive value is unknown.** |
| Migration chronology | EDGE's recorded transition sequence. Underlying observations are ordered by `observed_at`, then `received_at`, then insertion ID. Event-ID wording is not chronology. |

Production formation uses route-specific observation concentrations; activation
may also carry explicit operator-promotion provenance. Migration may retain or
change the owner when EDGE's successor conditions are met. Astra reads the
resulting authority and does not rerun or replace qualification rules.

Production activation and successor activation use the confirming observation's
`observed_at`; initial operator promotion uses the recorded promotion time.
Copy the authoritative timestamp and provenance without inferring one from the
other. Late observations can cause EDGE to reconcile derived history; preserve
the state actually available at T0 and append any later correction.

## Current two-MRZ dealing structure

When current and previous authoritative MRZs exist, their midpoints are the
two outer decision anchors of the active dealing range:

```text
currentMrzMidpoint  = midpoint(currentMrzLower, currentMrzUpper)
previousMrzMidpoint = midpoint(previousMrzLower, previousMrzUpper)

dealingRangeLow  = min(currentMrzMidpoint, previousMrzMidpoint)
dealingRangeHigh = max(currentMrzMidpoint, previousMrzMidpoint)
migrationEqm    = midpoint(currentMrzMidpoint, previousMrzMidpoint)

Higher core MRZ midpoint
          │
       MRZ EQM
          │
Lower core MRZ midpoint
```

Either current or previous may be the higher anchor. **Dealing range** means
this midpoint-to-midpoint interval. **MRZ EQM**, also called **Migration EQM**,
is its midpoint, distinct from an individual core midpoint, IPDA EQM, and the
route emitter's EQM20.
The local Display rounds each core midpoint and then Migration EQM to the
instrument's minimum tick. Record authoritative raw values and Display values
separately if they differ; do not silently correct one into the other.

The Display's **evidence envelope** instead runs from the lower of the two
core lower bounds to the higher of their upper bounds. It filters displayed
evidence and is distinct from the dealing range. The **MRZ EQM proximal zone**
is a configured symmetric region around Migration EQM inside that range.
An interaction with that zone is distinguishable from an exact EQM-level touch.

With valid configured current/previous data, the active Display geometry begins
on the first chart bar at or after current activation. It does not wait for
the first EQM interaction. Display visibility toggles are not authority changes.
If a predecessor is missing, do not invent a two-MRZ range.

## MRZ Display evidence

Use the configured MRZ Display's detections and CE levels as supplied. Settings,
chart timeframe, activation gating, the evidence envelope, and retention limits
affect visibility. Absence of a mark is not evidence that a pattern never existed.

| Term | Factual meaning in the local Display |
| --- | --- |
| Raw candles | The chart's open, high, low, and close over each selected interval. Record whether the current candle is still forming or confirmed. |
| PD arrays | Display-identified price structures and reference levels, including displacement, FVG, VI, and OB evidence. They are not automatic trading signals. |
| Displacement | A candle whose selected size, absolute open-to-close or high-to-low, exceeds the configured standard-deviation threshold. Direction is classified by close versus open; eligible confirmed candles are highlighted. |
| CE | Consequent encroachment: the halfway price of the relevant candle range or array bounds in this Display. It records geometry. |
| Displacement CE | `(high + low) / 2` of the displacement candle, including when displacement detection uses body size. |
| FVG | Fair value gap: a qualifying three-candle gap between the first and third candles' wick ranges. The Display applies its additional breakaway/runaway conditions and evidence filter; use its identified arrays. |
| FVG CE | Midpoint of the identified gap bounds: first-candle high and third-candle low for bullish orientation; third-candle high and first-candle low for bearish orientation. |
| VI | Volume imbalance: the Display's Classic Type 1 pattern, a gap from the preceding close to current open between two same-direction candles whose wick ranges overlap. This local detector uses candle prices, not measured volume imbalance. |
| VI CE | Midpoint of the preceding close and current open that bound the identified VI. |
| OB | Order block: the Display's identified five-candle pattern. The full high/low of the opposite-direction candle three bars before detection supplies its bounds; creation is registered at the confirmed pattern edge. |
| OB CE | `(OB top + OB bottom) / 2`. |

Display mitigation conventions differ by array: displacement CE records a later
candle-body intersection; FVG/VI record a later confirmed close through their CE
in the detector's specified direction. These display states do not prescribe
trading meaning and do not define OB invalidation.

## OB lifecycle

The intended lifecycle vocabulary is:

```text
CREATED → UNTOUCHED → INTERACTED → CE_INTERACTED
                                    │
                           still structurally VALID
                                    │
                               INVALIDATED → terminal
```

| Term | Factual condition |
| --- | --- |
| CREATED / UNTOUCHED | The OB is registered; no subsequent qualifying range interaction has been recorded. |
| OB interaction / INTERACTED | A later confirmed candle's high/low intersects the OB range, including its boundary. The interaction flag remains recorded. |
| OB CE interaction / CE_INTERACTED | A later confirmed candle's high/low includes the OB CE. The CE-interaction flag remains recorded. |
| VALID | No confirmed invalidation has occurred. Range interaction and CE interaction do not invalidate an OB. |
| OB invalidation / INVALIDATED | Bullish orientation: a confirmed close strictly below OB bottom. Bearish orientation: a confirmed close strictly above OB top. This state is terminal; the same OB never resurrects. |

The diagram is a vocabulary sequence, not a requirement to visit each state on
a separate bar. Range/CE interactions can occur together; invalidation does not
require a previously recorded touch. A close exactly on the invalidation boundary
does not meet the strict condition. These structural lifecycle conditions are
not entry/exit rules. Bullish OB does not mean buy; bearish OB does not mean sell.

## Raw price-action observations

Astra may describe liquidity sweeps, excursions beyond structure, acceptance,
rejection, failed breakouts/reclaims, compression, consolidation, chop,
expansion, repeated tests, tempo, and sequences of reactions even when Pine
does not label them. State the visible behavior, reference, and timeframe
behind each description. These are observational concepts whose trading
significance remains open; a sequence of observations does not automatically
establish a trading signal.

## Factual provenance

Definitions were checked against the repository's [README](../../README.md),
[state engine](../../app/state_engine.py), and local
[mRZ Display source](../../pine/mrz.pine). These links identify factual sources,
not additional trading doctrine. See the [scope notes](README.md#repository-scope-notes)
for source-status and configuration limitations.
