# Group Opportunity Radar — visual QA

Date: 2026-11-09

## Visual truth and implementation

- Reference screenshot: `/Users/tonywong/Downloads/group dashboard.png`
- Implemented route: `http://127.0.0.1:8792/mrz/watchlists?group=3&window=24H`
- Implementation captures: Codex in-app browser captures at 1754 × 864 and 390 × 844 (browser artifacts; not written into the repository).
- Comparison method: side-by-side inspection of the supplied reference and the rendered route, followed by DOM dimension checks at both breakpoints.

## Fidelity review

- Preserved the dark operational-dashboard composition, narrow left navigation, high-density group table, selected-group evidence workspace, four status cards, stacked location flow, event lanes, member table, and right-side management sheets.
- Kept the existing `/mrz/watchlists` deep link and canonical group memberships while relabeling the workspace as Group Opportunity Radar.
- Group search, time-window controls, row selection, contributor inspection, create/edit/duplicate/delete flows, and Manage Groups were exercised in the browser.
- The Create Group close and cancel actions were corrected so required-field validation no longer traps the sheet.
- The unsupported EDGE_BOT OTE integration is rendered as `Feed not connected` / `Not connected`; no synthetic counts, alerts, or dates are shown.
- Browser console after a clean load: no errors.

## Responsive validation

- Desktop: 1754 × 864; document client width and scroll width both 1754 px.
- Mobile: 390 × 844; document client width and scroll width both 390 px.
- Wide evidence tables remain inside their own horizontal scroll regions; there is no page-level horizontal overflow.
- Mobile restores the compact workspace header, stacks the controls and evidence cards, and keeps the selected group detail below the overview.

## Findings

- P0: none.
- P1: none.
- P2: none remaining.

## Result

passed
