# Design QA — MRZ Migration Directional Breakdown

## Reference

- Source: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-9eececac-1faa-4324-89ff-c0d6ef6f08ff.png`
- Local preview: `http://127.0.0.1:8794/mrz/watchlists?group=1&window=20D`
- Reviewed: 2026-11-16

## What was verified

- Desktop viewport: 1596 × 953; the migration total and Higher, Lower, and Unchanged controls fit within Event Activity without page overflow.
- Mobile viewport: 390 × 844; the page remains within the viewport and both directional controls and drill-down remain operable.
- Synthetic canonical QA data reconciles exactly: 2 migrations = 1 Higher + 1 Lower + 0 Unchanged + 0 Unknown.
- Higher drill-down shows the contributing symbol, migration time, previous and successor ranges, both midpoints, direction, and canonical evidence action.
- Lower drill-down shows the corresponding canonical ETHUSDT event with correct old and successor ranges.
- Unique-symbol count is visible in the drill-down summary.
- Unknown is hidden when zero and is covered by automated tests when evidence is missing or ambiguous.
- Existing 20D filtering, recent events, and Symbol Opportunity Candidates remain intact.
- No browser console errors or warnings were observed.

## Issues

- P0: none
- P1: none
- P2: none

final result: passed
