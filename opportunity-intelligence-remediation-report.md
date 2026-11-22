# EDGE 2.0 Opportunity Intelligence UI and Chart Interaction Remediation

Date: 2026-11-22

## Outcome

Local verdict: **GO for operator review**. Production deployment and remote push were not performed.

## Root cause

Zoom controls called the complete Opportunity Intelligence workspace renderer. The canvas resize observer and a competing CSS minimum-width rule then recalculated the surrounding grid, so a chart-domain interaction could resize or collapse parent layout. Docking also retained only the range preset, not the exact visible domain or selected evidence.

## Remediation

- Added a shared, bounded time-viewport model used by Opportunity Map and MRZ Migration Path window bounds.
- Changed zoom, pan, wheel, pinch, reset, and range controls to redraw only the chart canvas.
- Added mouse/touch pointer panning, horizontal-wheel panning, pinch zoom, keyboard pan/zoom/reset, and accessible viewport announcements.
- Preserved the replay cutoff as the maximum visible time.
- Made 90D and 30D exact domains even for sparse histories; All uses the complete eligible evidence span.
- Preserved exact visible start/end, selected evidence, range, and return context through docking.
- Restored the approved full-width Current Readout below the chart and event timeline.
- Kept canonical event selection, evidence links, All/Key timeline modes, maximize/restore, and the minimal docked component.

## Current Readout

The readout is populated from the active backend response and includes:

- IPDA Location
- Active MRZ range, midpoint, and route
- Latest Near Miss range, midpoint, and deviation when available
- Migration Structure
- Derived Route Hypothesis
- Opportunity Evidence State

Missing evidence is shown as Unavailable or Insufficient; no values are invented.

## Browser verification

- AMZN sparse data: exact 90D/30D domains, All span, zoom, pan, replay cutoff, maximize/restore, dock/maximize/restore/undock, responsive layout, and Current Readout passed.
- AAPL dense data: 11 observations, canonical timeline selection, All/Key modes, MRZ evidence, and Current Readout passed.
- BTCUSDT Migration Path: latest canonical record rendered and existing navigation/control state remained functional.
- Desktop 1754 × 896, tablet 1024 × 768, and narrow 760 × 900 layouts passed without page-level horizontal overflow.
- Browser console contained no errors or warnings.

## Automated verification

- Focused JavaScript tests passed.
- Focused Python contracts: 49 passed.
- Full non-Pine suite: 539 passed, 8 skipped.
- Diff whitespace validation passed.

## Data limitations

- Local AMZN has four observations, one active MRZ, and no Near Miss.
- Local AAPL is denser but remains backend-classified as Undetermined / Insufficient.
- Local BTCUSDT has one migration record. The local dataset does not contain a mature multi-migration structural history, so that state could not be visually demonstrated without fabricating data.
