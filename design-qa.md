# Group Radar Opportunity Intelligence UI Correction — design QA

Date: 2026-11-12

## Visual truth and implementation evidence

- Source visual truth: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-85caf0ed-c29e-4509-822d-2eb77be20dc0.png`.
- Source pixels: 1568 × 1003, RGB PNG.
- Browser-rendered implementation:
  - `qa-opportunity-intelligence/group-radar-overview-correction.png` — 1600 px desktop overview capture.
  - `qa-opportunity-intelligence/group-workspace-correction.png` — 1600 px selected-group capture.
  - `qa-opportunity-intelligence/symbol-opportunity-desktop-final.png` — 1600 × 1000 CSS viewport, 1× capture.
  - `qa-opportunity-intelligence/symbol-opportunity-tablet-final.png` — 1024 × 900 CSS viewport, 1× capture.
  - `qa-opportunity-intelligence/symbol-opportunity-mobile-final.png` — 390 × 844 CSS viewport, full-page capture, 1×.
- Combined comparison inputs:
  - `qa-opportunity-intelligence/opportunity-ui-comparison-final.png` — equal-height side-by-side full-view comparison.
  - `qa-opportunity-intelligence/opportunity-ui-comparison-focused.png` — full-width stacked comparison for readable typography, spacing, chart, assessment, and timeline inspection.
- Density normalization: both desktop captures are 1× CSS-pixel captures. The 1568 × 1003 source and 1600 × 1000 implementation were scaled proportionally in the comparison board; no density-only finding was filed.
- State: dark theme. The source uses the requested NBIS historical example; the local verified build uses canonical seeded AMZN data. Data-shape and layout were compared, but data-dependent marker quantity and labels were not treated as fidelity defects.

## Full-view comparison

- The corrected symbol state preserves the supplied hierarchy: unchanged EDGE sidebar, Opportunity Intelligence header, breadcrumb, compact structural facts, historical replay, dominant full-width time–price map, readable assessment, and chronological timeline.
- The implementation intentionally places replay directly above the map and assessment below it, matching the written brief's permitted layout while preserving more map width than the source's two-column lower region.
- Group Overview, Selected Group Workspace, and Symbol Opportunity Workspace are now mutually exclusive states. No narrow group table or duplicate group dashboard remains beside the symbol analysis.
- Desktop, tablet, and mobile use the same navigation hierarchy. At 1024 px and 390 px, the document width equals the viewport width; wide chart and table content scrolls inside its own region.

## Focused region comparison

- Header and breadcrumb: compact title, selected group, selected symbol, hypothesis, first-observed date, research state, IPDA location, and unverified entry state are visible without clipping.
- Time–price map: proportional time axis, actual price axis, route observations, MRZ bands, Near Miss treatment, Pressure observations, OTE unavailable legend, range controls, and canonical evidence selection are preserved.
- Replay: previous/play/next/latest and as-known-at selection remain adjacent to the chart; event and knowledge time remain explicit.
- Assessment: the five required questions are presented as short evidence-derived rows at full width.
- Timeline: compact rows include date/time, tracker, event, price/zone, and evidence detail. Rows are keyboard-selectable and highlight the corresponding map evidence. Histories longer than eight rows expose a native expandable full list with observed and known time retained in accessible row labels.
- Group Evidence: IPDA, MRZ Migration, Current Pressure, Near Miss, Group Event Timeline, members, and canonical drilldowns remain available in one expandable section in the group workspace.

## Required fidelity surfaces

- Fonts and typography: the existing EDGE system-sans stack, display weight, compact table headers, muted metadata, and operator hierarchy are retained. No unintended wrapping or truncation was observed in the final desktop, tablet, or mobile captures.
- Spacing and layout rhythm: full-width workspaces replace the former split-pane composition. Panel padding, border density, radii, and vertical rhythm remain consistent with the existing EDGE shell.
- Colors and visual tokens: the existing near-black surfaces, mint accent, purple Near Miss, red Lower Pressure, cyan Higher Pressure, amber structure, and muted borders are reused.
- Image quality and assets: the existing EDGE logo is preserved. The source contains no new photographic or illustrative assets, so no placeholder, custom SVG, CSS illustration, or generated asset was introduced.
- Copy and content: research language remains evidence-derived. OTE stays unavailable and entry remains explicitly not verified.
- Accessibility and interaction: native buttons, tables, details/summary expansion, focus states, keyboard row activation, reduced-motion behavior, labelled replay/map controls, and responsive internal scrolling are retained.

## Comparison history

- Pass 1 finding [P1]: the original implementation displayed the full group table, candidate rail, symbol analysis, and full group evidence simultaneously.
  - Fix: introduced URL-backed Overview, Group Workspace, and Symbol Workspace states with explicit breadcrumb/back navigation.
  - Post-fix evidence: the three state-specific desktop captures listed above.
- Pass 1 finding [P2]: replay and chart range controls inherited the generic panel-title grid rule and stacked vertically, creating excess empty height.
  - Fix: gave both control groups an explicit horizontal flex layout.
  - Post-fix evidence: `symbol-opportunity-desktop-correction-v2.png`.
- Pass 2 finding [P2]: the initial desktop chart height pushed the assessment entirely below the 1000 px viewport.
  - Fix: reduced the desktop canvas height while preserving a taller, horizontally pannable mobile canvas.
  - Post-fix evidence: `symbol-opportunity-desktop-final.png` and `symbol-opportunity-mobile-final.png`.
- Pass 3: compared the final 1600 px build with the source in the combined comparison inputs, exercised replay, event selection, group back navigation, and Group Evidence expansion, then checked 1024 px and 390 px layouts. No actionable P0/P1/P2 findings remain.

## Primary interactions tested

- Opened AI Clouds from Group Overview and verified the overview disappeared.
- Opened AMZN from the full-width candidate table and verified the group dashboard disappeared.
- Used the group breadcrumb to return without losing the selected group.
- Selected a timeline event and verified one selected row plus populated canonical event detail and chart highlighting.
- Moved Historical Replay to the previous cursor and verified the as-known-at note changed.
- Expanded Group Evidence and verified MRZ Migration content became visible.
- Browser console: zero errors in the final symbol pass.

## Findings

- P0: none.
- P1: none remaining.
- P2: none remaining.
- P3: source and local verification use different canonical symbols, so exact marker density was validated structurally rather than pixel-for-pixel.

## Final result

passed
