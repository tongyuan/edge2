# Design QA — Group Radar and Opportunity Map Near Miss

## Reference

- Approved source: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-aa4cc9c4-7d7f-47d1-8ccc-f7fe2b33b674.png`
- Source dimensions: 1754 × 897
- Local preview: `http://127.0.0.1:8794/mrz/watchlists?group=all&window=5D`
- Opportunity Map QA: `http://127.0.0.1:8794/mrz/watchlists?group=1&window=5D&symbol=BMNR`
- Reviewed: 2026-11-17

## What was verified

- Desktop viewport: 1754 × 897 for the approved Group Radar composition and 1280 × 800 for the interactive drawer and Opportunity Map checks.
- Group Radar retains the three top summary cards and uses the approved six-column table: Group, Members, IPDA Breadth, Location Flow, Structural Events, and Open.
- Structural event badges expose NM, ACT, and MRZ counts; zero badges remain visible and disabled.
- The Crypto MRZ badge opens a right-side drawer with Total, Higher, Lower, and Unchanged reconciliation, contributing symbols, previous/next ranges, timestamps, direction, and evidence links.
- Mobile viewport: 390 × 844. The page has no document-level horizontal overflow; the six-column table scrolls inside its own region.
- The mobile evidence drawer occupies the full viewport. Its table scrolls internally and its Group Evolution action remains reachable.
- The BMNR Near Miss candidate begins at its actual event time and extends approximately 48 CSS pixels to the right without changing the chart time axis.
- Selecting the Near Miss redraws the dashed outline above the observation markers and exposes compact canonical evidence details.
- The All / 90D / 30D controls, canonical evidence action, replay controls, Group Evolution, and existing Inbox remain present.
- Browser console review reported no errors or warnings.

## Issues

- P0: none
- P1: none
- P2: none

final result: passed
