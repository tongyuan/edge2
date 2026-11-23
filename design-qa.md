# EDGE 2.0 MRZ Migration Path — visual QA

Date: 2026-11-22

## Reference and implementation

- Approved reference: `/Users/tonywong/Downloads/symbol.png`
- Local implementation: `http://127.0.0.1:8792/mrz/symbols?symbol=BTCUSDT`
- Same-width browser capture: `artifacts/mrz-limited-btcusdt.jpg`
- Active-state capture: `artifacts/mrz-active-badge-ethusdt.jpg`
- Dense interaction fixture: `artifacts/mrz-fixture-mature-initial.jpg`

## Comparison history

1. P1 — The path omitted the initial activation state. Fixed by returning and rendering activation plus migration states while keeping migration-event counts separate.
2. P1 — Selected evidence was populated into an element that CSS permanently hid. Fixed with an explicit selected-state overlay containing state identity, bounds, midpoint, route, event time, first-known time, structural pivot and canonical reference.
3. P1 — Maximize visually stretched a 300px backing canvas. Fixed by redrawing at the actual expanded or docked dimensions.
4. P1 — Docking did not preserve the current state selection or viewport. Fixed by carrying window start, window size and canonical event identity through Dock and Undock.
5. P2 — Zero-history symbols showed a generic empty message without explaining eligibility. Fixed with a canonical-data explanation and no misleading generation action.
6. P2 — The symbol heading displayed `MRZ ACTIVE` as unstyled text with a white dot. Fixed to match the approved compact green outlined pill.
7. Final same-viewport comparison — the page hierarchy, three-column proportions, compact summary strip, chart panel, structural context, tabs, recent events and active-state treatment match the approved design intent. Data values differ because the local database does not contain the illustrative NBIS history.

## Visual and interaction verification

- Desktop 1754 × 896: verified against the approved reference.
- iPad 820 × 1180: document width remained 820px; chart and toolbar stayed inside the viewport.
- iPhone 390 × 844: document width remained 390px; summary cards and migration launcher stacked without horizontal overflow.
- Dense isolated fixture: zoom, Earlier/Newer, selection evidence, maximize, restore and reset rendered without changing canonical coordinates.
- Docked layout: chart redrew from 1710 × 744 to 716 × 408 when resized and retained state selection and viewport parameters.
- Active MRZ badge: computed color `rgb(56, 226, 169)`, border `rgb(22, 183, 127)`, translucent green background and 999px radius.
- Keyboard selection exposes canonical evidence. Mouse/trackpad wheel and touch pinch handlers are implemented, but direct gesture synthesis was not available in the browser-control surface.

## Data limitations observed

- No local symbol has four or more migration events.
- BTCUSDT, AAPL, SMH and 9988.HK each have one migration and two distinct canonical states.
- ETHUSDT and 0700.HK each have one activation state and no migration event.
- Dense screenshots use a clearly labelled, in-memory/disposable fixture outside PostgreSQL; they do not establish production-data readiness.

## Automated verification

- JavaScript migration-path and docking tests passed.
- Full local non-Pine suite: 541 passed, 8 skipped, 0 failed.
- Production, production data and the remote repository were not changed.

## Opportunity Map toolbar icon alignment — 2026-11-23

- Source visual truth: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-4f1c98b6-89eb-4489-b421-85d49917b94a.png` (MRZ Migration Path toolbar).
- Supporting before-state: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-11ce134a-1c74-4246-889d-bd13c172d2e4.png`.
- Implementation: `http://127.0.0.1:8792/mrz/watchlists?group=5&window=20D&symbol=BTCUSDT`.
- Implementation screenshot evidence: in-app Browser capture emitted during this QA run; the browser surface does not provide a filesystem-backed screenshot path.
- Desktop viewport: 1440 × 900 CSS px, density 1. The focused toolbar comparison used the rendered Opportunity Map header at the same native CSS scale as the source control row.
- Mobile viewport: 390 × 844 CSS px, density 1. Document width and viewport both measured 390px.
- State: BTCUSDT Opportunity Map, 90D selected, non-maximized.

### Focused comparison

- Control order now matches Migration Path: zoom out, zoom in, reset, dock, maximize.
- Visible controls use the same icon set: `−`, `+`, `↺`, the existing detach-window icon, and `⛶`; maximize changes to `↙` while active.
- Buttons use the same 32px width, 30px minimum height, 5px gap, border, dark fill, hover/focus system and tooltip/accessibility labels as Migration Path.
- The Opportunity Map range controls remain distinct and unchanged.

### Required fidelity surfaces

- Fonts and typography: unchanged from the existing EDGE control system; no new text labels remain in the icon toolbar.
- Spacing and layout rhythm: matches the Migration Path compact toolbar sizing and order; mobile toolbar remains within the 390px viewport.
- Colors and visual tokens: reuses existing `quiet-button`, `chart-workspace-controls` and dock icon tokens.
- Image/icon fidelity: reuses the existing application icon treatment; no replacement raster or custom SVG asset was introduced.
- Copy/content: tooltip and accessible labels remain explicit for Zoom out, Zoom in, Reset chart view, Dock Opportunity Map and Maximize/Restore chart.

### Interaction verification

- Zoom in changed the visible domain from 25 Aug–23 Nov to 6 Sept–11 Nov.
- Reset restored 25 Aug–23 Nov.
- Maximize applied the expanded state and changed the icon/label to Restore; Restore returned to the normal state.
- Mobile document width reconciled exactly with the viewport; no horizontal overflow was introduced.
- No P0, P1 or P2 visual mismatch remains for this focused control update.

final result: passed
