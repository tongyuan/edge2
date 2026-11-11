# Current Pressure Intelligence — design QA

Date: 2026-11-11

## Visual truth and implementation evidence

- Source visual truth: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-cc67abab-488a-4bca-b95c-ef9fc83b76f5.png`
- Source pixels: 1672 × 941, RGB PNG. The source is a three-screen desktop composition rather than one browser viewport.
- Browser-rendered implementation:
  - `qa-current-pressure/symbols-nvda-desktop-final.png` — 1440 × 900 desktop viewport, 1× capture.
  - `qa-current-pressure/group-radar-mag7-desktop.png` — 1440 × 900 CSS viewport, full-page 1440 × 1439 capture, 1×.
  - `qa-current-pressure/events-aapl-desktop.png` — 1440 × 900 desktop viewport, 1× capture.
  - `qa-current-pressure/symbols-nvda-mobile.png` — 390 × 844 CSS viewport, full-page 390 × 1341 capture, 1×.
- Combined comparison input: `qa-current-pressure/comparison-board.jpg` — 1672 × 1760. The unchanged source composition and all three desktop implementation surfaces were placed in one comparison board before judging.
- Density normalization: all browser captures are 1× CSS-pixel captures. The source was retained at native size and scaled proportionally only inside the comparison board; no density-only finding was filed.
- State: dark theme; real local canonical/test data. NVDA demonstrates Lower 4/4 evidence, MAG7 demonstrates a mixed group with the compact gauges, and a clearly labeled local QA observation sequence demonstrates one future-only AAPL Current Pressure → Higher transition.

## Full-view comparison

- Information architecture follows the source: persistent EDGE navigation, compact operator header, three-card symbol inspection, a full-width pressure timeline, dense current-pressure cells in the group member table, and a filtered canonical event table.
- The existing product organizes Group Radar as a group overview followed by selected-group evidence. Current-pressure gauges therefore appear in the selected group’s symbol rows rather than replacing the established group overview table. This is an intentional architecture constraint; the symbol-level scan remains one click from the overview.
- Desktop composition, dark surface hierarchy, border density, compact table rhythm, mint/red/neutral semantics, and operator-focused typography match the source intent without introducing a parallel design system.
- Mobile 390 px validation stacks the three symbol cards, preserves four readable evidence cells, keeps the timeline legible, and uses the existing mobile navigation without page-level horizontal overflow.

## Focused region comparison

- Symbol evidence card: verified direction headline, 4/4 denominator, R/X cells, route/type tooltips, price/date, latest-evidence age, migration envelope, lifecycle identity, and R/X plus envelope-side legend.
- Group member rows: verified compact cells only for observations that exist, Higher/Lower/Neutral label, visible evidence freshness, MRZ/route/location, Near Miss, OTE, status, and an accessible symbol deep link on the gauge.
- Events table: verified Current Pressure Changed is distinct from Historical Cumulative Pressure, shows previous → current state, evidence counts, date, symbol, and symbol deep link. The type filter returns exactly the current-pressure event in the exercised AAPL state.

## Required fidelity surfaces

- Fonts and typography: existing system sans family retained; display headings, compact table headers, evidence numerals, and secondary metadata preserve the source hierarchy. No clipping or unintended truncation was observed at desktop or 390 px.
- Spacing and layout rhythm: card gaps, panel padding, table density, radii, and dividers align with the existing EDGE shell and the supplied mock. The timeline spans the full card grid as in the source.
- Colors and tokens: existing surface, line, mint, red, amber, blue, and muted tokens are reused. Higher, Lower, Neutral, authority, cumulative pressure, and Near Miss remain visually distinct with sufficient contrast.
- Image quality and assets: the existing EDGE product mark is preserved. The target contains no new photographic or illustrative asset; no placeholder, custom SVG substitute, CSS art, or generated imagery was introduced.
- Copy and content: labels use Current Pressure for the latest-4 classifier and Historical Cumulative Pressure for the legacy cumulative event. Empty and future-only states explicitly avoid implying reconstructed history.
- Icons and semantics: arrows are data-direction notation required by the brief; R/X is explicitly decoded in the UI. Existing shell icons are unchanged.
- Accessibility and interaction: native links, table semantics, labels, select controls, tooltips/titles, focus styles, reduced-motion rules, and mobile navigation are retained. Current Pressure filtering and group-to-symbol navigation were exercised.

## Comparison history

- Pass 1 finding [P2]: the no-evidence paragraph occupied one of four grid columns and wrapped vertically in the symbol pressure card.
  - Fix: span the empty evidence state across all four grid columns with `.pressure-evidence-empty { grid-column: 1 / -1; }`.
  - Post-fix evidence: the AAPL empty state renders as one readable full-width sentence; NVDA’s four evidence cells remain unchanged.
- Pass 1 finding [P2]: R/X and envelope-side semantics were visible in individual cells/tooltips but lacked a persistent on-card legend.
  - Fix: added `R = Reclaim · X = Rejection · ↑ above envelope · ↓ below envelope` below the evidence cells.
  - Post-fix evidence: `qa-current-pressure/symbols-nvda-desktop-final.png`.
- Pass 2 finding [P2]: the group gauge initially padded short sequences with visually empty slots, which implied four observations where fewer existed.
  - Fix: render only canonical supporting observations; no placeholder segments are manufactured.
- Pass 2 finding [P2]: the group pressure text exposed an Open action elsewhere in the row, but the gauge itself was not actionable.
  - Fix: made the whole gauge an accessible link to the selected symbol inspection and added visible evidence age.
- Pass 3: re-captured the updated surfaces at 1440 × 900, checked the browser console (no warnings or errors), exercised the Current Pressure event filter, and rechecked the 390 px responsive state. No actionable P0/P1/P2 issues remain.

## Primary interactions tested

- Opened MAG7 from the Group Radar overview and verified selected-row state plus symbol gauges.
- Opened symbol inspection directly with NVDA and verified current evidence plus timeline.
- Opened Events History with AAPL symbol scope and filtered to `CURRENT_PRESSURE_CHANGED`; one matching row remained.
- Checked desktop 1440 × 900 and mobile 390 × 844 layouts.
- Browser console: no warnings or errors in the final symbol pass.

## Findings

- P0: none.
- P1: none.
- P2: none remaining.
- P3: the source mock shows a dedicated event-history transition toggle; the implementation uses a precise native type filter instead. This is functionally equivalent and consistent with the existing filter model.

## Final result

passed
