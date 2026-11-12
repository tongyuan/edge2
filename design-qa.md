# Opportunity Intelligence UI Follow-up — design QA

Date: 2026-11-12

## Visual truth and implementation evidence

- Source visual truth:
  - `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-64cfc346-d65c-48a2-9343-3b9ead419a96.png` — Group Overview search field to remove.
  - `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-f78b5d6c-6f3c-4430-a099-5a01afe17d28.png` — combined marker legibility issue.
  - `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-a9186571-e8a7-46b8-94d0-93fd19552e9f.png` — eight-row timeline with inaccessible full-record presentation.
- Source pixels: 1916 × 175, 1595 × 771, and 1588 × 545 respectively, at the supplied capture density.
- Browser-rendered implementation: local staging at `http://127.0.0.1:8792`, checked in the Codex in-app browser at the default 1440 × 1000 CSS viewport and 390 × 844 CSS viewport.
- Current implementation captures were inspected inline during browser QA. The in-app browser does not expose capture bytes as writable project files, so no new screenshot file was persisted.
- State: dark theme with Group Overview and AAPL Opportunity History using canonical seeded evidence. Collapsed and fully expanded timeline states were inspected.

## Full-view comparison

- Group Overview now moves directly from the group count to sorting and management actions; the search field and its reserved width are gone.
- The existing EDGE sidebar, typography, panel treatment, activity summary, sort control, New Group action, and group table remain unchanged.
- Opportunity Map geometry, axes, structural bands, event timing, and canonical data are unchanged.
- Timeline expansion retains one table, replaces its body with the complete canonical record set, and removes the vertical height cap so the page exposes every row.
- At 390 px, the document width remains exactly 390 px. Dense table content stays horizontally pannable inside its own region.

## Focused comparison

- Combined marker: a pressure-colored triangle outline now encloses a route-colored center dot. The two classifications read as one canonical marker without the filled-triangle/white-ring stacking seen in the source screenshot.
- Route-only observations remain blue or violet filled circles. Pressure-only observations remain filled directional triangles.
- Timeline: AAPL renders 8 of 13 records while collapsed. Activating View all renders all 13 rows, applies the expanded state, and produces `clientHeight === scrollHeight` (588 px), proving there is no hidden internal vertical record area. The control changes to `Show first 8 events`.
- Group toolbar: DOM verification reports zero `#groupEvidenceSearch` or `.radar-search` elements while retaining one sort control and both group-management actions.

## Required fidelity surfaces

- Fonts and typography: existing EDGE font family, compact weights, header hierarchy, table type, and metadata sizing are retained.
- Spacing and layout rhythm: removal of the search track closes the large empty middle field; sort and group actions align naturally without a placeholder gap.
- Colors and visual tokens: existing dark surfaces and evidence colors are retained. The combined marker uses the exact route and Pressure colors already established by the legend.
- Image quality and assets: no raster, illustration, logo, or placeholder asset was added or changed.
- Copy and content: only the expansion label changed from `Show fewer` to the more explicit `Show first 8 events`; canonical event copy and record counts are unchanged.
- Accessibility and interaction: the expansion control retains `aria-expanded`; every expanded timeline row remains keyboard-selectable; mobile document overflow remains contained.

## Comparison history

- Pass 1 [P1]: full-record mode remained inside a 420 px internally scrolling region, making the additional rows easy to miss and preventing a true all-record page view.
  - Fix: expanded mode removes the height cap and renders the full canonical row set in the single table.
  - Post-fix evidence: 13 rows, expanded class present, 588 px client height, 588 px scroll height.
- Pass 1 [P1]: combined route/Pressure markers read as a filled triangle and separately stacked circle with a bright white separator.
  - Fix: use a pressure-colored triangle outline with a dark interior and route-colored center dot.
  - Post-fix evidence: the desktop AAPL chart visibly presents one coherent outlined marker per shared classification.
- Pass 1 [P2]: removing only the search element would have left a wide empty grid track.
  - Fix: change the toolbar to three tracks and realign its tablet/mobile rules.
  - Post-fix evidence: default and 390 px Group Overview captures show a compact toolbar with no empty search gap or page overflow.
- Pass 2: repeated desktop and mobile checks. No actionable P0/P1/P2 findings remain.

## Primary interactions tested

- Opened Group Overview and verified the search field is absent.
- Opened AAPL Opportunity History and inspected the revised combined markers.
- Expanded the timeline from 8 to all 13 records and verified the full table is not vertically capped.
- Checked the same Group Overview and expanded timeline at 390 × 844.
- Browser console: zero errors.

## Findings

- P0: none.
- P1: none remaining.
- P2: none remaining.
- P3: dense event tables still require horizontal panning on mobile, intentionally contained within the table region.

## Final result

passed
