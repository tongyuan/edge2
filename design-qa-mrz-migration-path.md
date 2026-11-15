# MRZ Migration Path — Design QA

## Reference

- Source: `/Users/tonywong/Downloads/EDGE Intel MRZ Migration Dashboard.png`
- Reference viewport: 1710 × 921 px
- Target state: Canonical Symbol Inspection with a generated multi-record migration path

## Implementation inspected

- Local preview: `http://127.0.0.1:8794/mrz/symbols?symbol=ETHUSDT`
- Desktop viewport: 1710 × 921 px
- Mobile viewport: 390 × 844 px
- Browser: Codex in-app browser
- Current implementation captures were inspected inline during browser QA. The in-app browser does not expose capture bytes as writable project files, so no new screenshot file was persisted.

## Visual comparison

- The selected-symbol authority card and migration launcher preserve the approved two-column desktop hierarchy.
- The launcher uses the approved title, explanatory copy, live migration count, and green full-width action.
- The generated path spans the full workspace width above Near Miss History.
- The chart uses violet structural ranges, green midpoint markers, dashed green progression, event sequence labels, event-time x-axis, linear price y-axis, and a latest-record detail card.
- On mobile, the launcher, chart, record details, and controls stack without clipping; the chart remains horizontally scrollable.

## Interaction and data states

- Multi-record history: passed (ETHUSDT, three canonical migrations).
- Record selection: passed (selecting the first marker changed details from sequence 4 to sequence 2).
- Hide/show behavior: passed.
- Single-record history: passed (NVDA, includes verified previous MRZ and limited-history note).
- Empty history: passed (AAPL, no generate action rendered).
- Symbol changes reset generated state: passed.
- Console warnings/errors: none.

## Iteration history

- Initial implementation was inspected against the reference at its native desktop size.
- Responsive behavior was then verified at 390 × 844 px.
- No P0, P1, or P2 visual or interaction defects remained after inspection.

## Final result

passed
