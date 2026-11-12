# Opportunity Intelligence UI Cleanup — design QA

Date: 2026-11-12

## Visual truth and implementation evidence

- Source visual truth: the existing corrected EDGE workspace captured at `qa-opportunity-intelligence/symbol-opportunity-desktop-final.png`, plus the operator cleanup and Opportunity Map refinement briefs attached on 2026-11-12.
- Baseline implementation screenshot: `qa-opportunity-intelligence/symbol-opportunity-desktop-final.png` at a 1600 × 1000 CSS viewport and 1× density.
- Browser-rendered implementation: local staging at `http://127.0.0.1:8792`, checked in the Codex in-app browser at 1440 × 1000, 1024 × 900, and 390 × 844 CSS viewports.
- Current implementation captures were inspected inline during browser QA. Browser security prevented persisting those capture bytes as new project files; this does not affect the rendered comparison or interaction checks.
- State: dark theme with canonical seeded AAPL evidence. Group Overview, Symbols, normal Opportunity History, expanded timeline, historical replay, maximized map, restored map, tablet, and mobile states were inspected.

## Full-view comparison

- The existing EDGE layout, sidebar, typography, panel treatment, and navigation hierarchy are unchanged.
- OTE-only columns, cards, legend content, empty messages, and timeline lane are removed; remaining content reclaims the width without empty containers.
- Symbols now uses the selected-symbol, Current Pressure, and MRZ Context panels only. Current Pressure retains the latest qualifying observations and Events History remains available.
- The Opportunity Map retains its dominant position and now has compact chronological replay controls plus Maximize/Restore without introducing a new route.
- Tablet and mobile document widths equal their viewports. The chart remains internally pannable at mobile width rather than causing page-level overflow.

## Focused comparison

- Replay: the native range control exposes a visible thumb, exact chronological minimum/maximum, keyboard semantics, pointer/touch dragging, Previous/Play/Next controls, a selected timestamp, and Latest.
- Replay correctness: dragging AAPL from latest to 10 Nov reduced the visible assessment from 11 to 8 canonical route/IPDA observations and the unique timeline count from 13 to 10; Latest restored the current evidence.
- Map markers: BTD is blue, STR violet, Higher Pressure an upward green triangle, Lower Pressure a downward coral triangle, MRZ a teal band, and Near Miss a dashed purple band. Shared route/Pressure observations render as one combined marker and one canonical timeline row.
- Maximize: the map fills the application viewport, preserves axes, structural bands, markers, legend, selected-event details, range state, replay state, and selected event. Restore and Escape both work.
- Timeline: one table renders eight rows when collapsed and all 13 unique AAPL records when expanded. The toggle becomes Show fewer and restores eight rows. Observed and known times are both visible.
- Price axis: AAPL ticks use two decimals while exact canonical prices remain available in selected-event details.

## Required fidelity surfaces

- Fonts and typography: existing EDGE system-sans family, weights, compact headers, readable metadata, and hierarchy are retained with no new clipping.
- Spacing and layout rhythm: removed panels collapse cleanly; three evidence cards and the narrower tables redistribute available width consistently.
- Colors and visual tokens: existing dark surfaces and borders are retained. Only evidence colors were changed to the operator-specified blue, violet, green, coral, teal, and light-purple values.
- Image quality and assets: the existing EDGE logo remains unchanged; no new raster, illustration, logo, or placeholder asset was introduced.
- Copy and content: OTE-specific presentation is absent. Research-only language and the Not verified execution boundary remain intact.
- Accessibility and interaction: replay uses a native labelled range input, timeline rows remain keyboard-selectable, Maximize exposes pressed state and an accessible Restore label, Escape restores the map, and touch targets remain usable at 390 px.

## Comparison history

- Pass 1 [P1]: timeline expansion mounted the eight-row preview and a second full table, duplicating the preview records.
  - Fix: one canonical event array is deduplicated by stable canonical identity and rendered through one table body that switches between `slice(0, 8)` and the full set.
  - Post-fix evidence: one table / 8 rows collapsed, one table / 13 rows expanded, and one table / 8 rows after Show fewer.
- Pass 1 [P2]: replay used discrete selection and an ornamental progress bar, so direct chronological movement was unavailable.
  - Fix: replaced it with a native draggable range using epoch-time bounds, debounced as-known-at loading, visible timestamp, checkpoint precision controls, and Latest.
  - Post-fix evidence: pointer drag changed the cursor, chart evidence, assessment, and timeline count without reloading the page.
- Pass 1 [P2]: route observations and Pressure classifications were plotted as unrelated overlapping circles.
  - Fix: canonical identities are merged; combined events use a Pressure triangle with a route-colored center and one selected-event record.
  - Post-fix evidence: AAPL combined rows show `IPDA_ROUTE + PRESSURE` once and combined markers remain individually selectable.
- Pass 2: checked normal/maximized/restored map states and 1024 px / 390 px layouts. No actionable P0/P1/P2 findings remain.

## Primary interactions tested

- Dragged the replay slider and returned with Latest.
- Selected a timeline row and verified the map selection plus exact canonical details.
- Switched to 90D, maximized the map, restored with Escape, and verified the 90D range and selected event persisted.
- Expanded 13 unique AAPL events, verified one table, then collapsed to eight rows.
- Opened Symbols for AAPL and verified exactly three upper evidence panels with Current Pressure observations intact.
- Opened Group Overview and verified no OTE labels or empty OTE space remain.
- Checked page overflow at 1024 px and 390 px; document widths matched the viewport.
- Browser console: zero errors.

## Findings

- P0: none.
- P1: none remaining.
- P2: none remaining.
- P3: maximized portrait/mobile layouts necessarily leave vertical breathing room because the wide chart preserves its aspect ratio; horizontal panning keeps every price/time detail available.

## Final result

passed
