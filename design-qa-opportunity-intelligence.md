# Opportunity Intelligence Phase 1 — Design QA

## Reference and implementation

- Reference: `/Users/tonywong/Downloads/opp detection.png` (1568 × 1003)
- Desktop implementation: `qa-opportunity-intelligence/group-radar-desktop-final.jpg` (1600 × 1000)
- Mobile implementation: `qa-opportunity-intelligence/group-radar-mobile-final.jpg` (390 × 844)
- Route: `/mrz/watchlists?group=1&window=24H`
- Review date: 2026-11-12

## Findings

| Priority | Finding | Resolution |
| --- | --- | --- |
| P1 | The first pass stacked the selected-group opportunity workspace below the legacy all-groups table, pushing the map and replay controls below the desktop fold. | Fixed. Selected-group mode now uses a left group list and right opportunity workspace, with the group-level opportunity summary spanning the top. |
| P2 | The selected-group table carried all twelve legacy evidence columns and overwhelmed the left rail. | Fixed. Desktop selected-group mode shows the five decision-relevant columns; the complete evidence table remains available in the stacked responsive layout. |
| P2 | The selected-group opportunity summary duplicated the top summary after the layout change. | Fixed. The nested duplicate is hidden only in desktop split view and remains available in stacked layouts. |

## Verification

- No P0, P1, or open P2 visual issues remain.
- Desktop hierarchy, color language, split composition, candidate rail, time-price map, replay controls, event timeline, and assessment follow the supplied reference while retaining the existing EDGE shell.
- Mobile preserves the complete workflow in a single-column layout and keeps the chart horizontally navigable.
- Candidate selection changes the symbol workspace correctly.
- Historical replay refetches at the selected knowledge-time cursor and continues to distinguish event time from known time.
- Browser console: no errors during desktop, mobile, candidate-selection, or replay checks.
- Live preview data differs from the reference fixture by design; no production facts were fabricated to force visual parity.

## Final result

passed
