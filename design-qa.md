# Design QA — Group Workspace and Group Evolution

## Reference

- Source: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-861bf9bb-2757-4aa4-a495-a2f9f673ab8f.png`
- Local preview: `http://127.0.0.1:8794/mrz/watchlists?group=1&window=20D`
- Reviewed: 2026-11-16

## What was verified

- Desktop viewport: 1672 × 941
- Mobile viewport: 390 × 844
- Group title, member count, time selector, Edit Group, and As Of share the group header.
- Redundant group summary cards are absent from the Group Workspace.
- Group Evolution contains IPDA Location Flow and Structural Transitions on the first row.
- The zero-transition state is compact and does not render a candidate table.
- Event Activity is full-width and contains canonical Near Miss, MRZ Activation, and MRZ Migration counts plus three recent events.
- Symbol Opportunity Candidates remain present with their existing fields and actions.
- Inbox remains available in the shared header.
- The Near Miss history heading reads `Observed at (UTC−4)` and uses the shared fixed UTC−4 formatter.
- No browser console errors were observed.

## Issues

- P0: none
- P1: none
- P2: none

final result: passed
