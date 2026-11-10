# Group Radar Activity & Change Detection — visual QA

Date: 2026-11-11

## Visual truth and implementation

- Reference screenshot: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-275a0d51-0428-4138-b09c-7e5634511378.png`
- Implemented route: `http://127.0.0.1:8792/mrz/watchlists?group=all&window=20D`
- Drilldown route/state: Crypto & DAT, 20D, activity drawer open.
- Implementation captures: Codex in-app browser full-page captures at the default narrow viewport and at 1440 × 1000 (browser QA artifacts; not written into the repository).
- Comparison method: full-view comparison of the reference and rendered overview, followed by a focused comparison of the highlighted Activity column and right-side group activity drawer.

## Fidelity surfaces

- Layout: preserved the EDGE navigation, dense group table, three summary cards, selected-group workspace, and right-side drilldown from the reference while retaining the existing evidence workspace below the overview.
- Typography: retained the app's existing compact operational hierarchy; activity totals, group names, and record types use stronger weight while timestamps and coverage explanations remain secondary.
- Color: uses the established mint, blue, yellow, red, and purple tracker palette; insufficient coverage is deliberately neutral/yellow rather than being shown as a verified no-change state.
- Spacing and sizing: summary cards align as one desktop row and stack at the narrow breakpoint; the activity drawer has consistent internal spacing and remains a full-width overlay on narrow screens.
- Content and behavior: the dynamic Activity heading follows 24H/5D/20D, activity records are newest-first with exact timestamps and deep links, and OTE remains explicitly not connected.

## Interaction and responsive validation

- Exercised 24H, 5D, and 20D windows. The 24H view correctly shows `Insufficient data` when no member has a fresh comparable observation; 5D and 20D show only persisted tracker records in their windows.
- Exercised `Most Recent Activity` and `Group Name A–Z`; alphabetical sorting begins with AI Clouds and does not alter evidence data.
- Opened the Crypto & DAT activity cell and verified the responsive drawer, tracker counts, comparison coverage, exact MRZ/pressure records, member context, close action, and full-evidence action.
- Desktop validation: 1440 × 1000. The summary cards, highlighted Activity column, selected row, detailed evidence workspace, and fixed-width right drawer remain legible without page-level overflow.
- Narrow validation: default 721 px viewport. Controls and summary cards stack, the table remains in its horizontal scroll region, and the drawer becomes a full-width overlay.
- Browser console: no warnings or errors after the overview, sort, timeframe, and drilldown checks.

## Comparison history

- Pass 1: narrow 20D overview confirmed stacked summary cards, dynamic Activity column, and horizontal table containment.
- Pass 2: narrow activity drilldown confirmed record ordering, coverage disclosure, member context, and responsive full-width presentation.
- Pass 3: desktop overview and drilldown confirmed reference-aligned hierarchy, table density, selected-row treatment, and right-panel composition.
- Pass 4: 24H and 5D states confirmed timeframe changes, conservative insufficient-data semantics, and stable current-state columns.

## Findings

- P0: none.
- P1: none.
- P2: none remaining.

## Result

passed
