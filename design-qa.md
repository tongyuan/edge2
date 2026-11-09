# Structural Location Transition Heatmap — Design QA

## Scope

- Reference: `codex-clipboard-27ac0127-0724-4fb2-bf90-55e21d75ae06.png`
- Reference: `codex-clipboard-f11ab65e-ff27-4f4f-845b-cb7654193e04.png`
- Implementation: `/mrz/location-distribution` in the isolated EDGE 2.0 test runtime
- Desktop viewport: 1280 × 720, full-page capture reviewed
- Mobile viewport: 390 × 844, full-page capture and contributor drill-down reviewed

## Comparison

| Area | Reference intent | Implementation result | Status |
| --- | --- | --- | --- |
| Movement summary | Three compact factual totals above the matrix | Moved Higher, Moved Lower, and Same Bucket appear first with distinct green, red, and grey emphasis | Passed |
| Matrix geometry | Compact fixed 5 × 5 grid with rows as previous location and columns as current location | All 25 cells render in the required Deep Discount → Deep Premium ordering | Passed |
| Direction color | Right of diagonal green, left red, diagonal grey, zeros dim | Direction is derived from fixed bucket indices and represented with color-independent labels and tooltips | Passed |
| Density | Count-proportional emphasis without decorative graphics | Each directional family scales against its own maximum; zero cells remain visually quiet | Passed |
| Data context | Clear selected window and factual support | Header, selected 24H/5D/20D control, freshness coverage, exact endpoints, and elapsed-time semantics are visible | Passed |
| Drill-down | Populated cells reveal exact constituents | Desktop and mobile drill-downs show symbol, endpoints, movement, observation times, freshness, and symbol link | Passed |
| Mobile | Matrix and detail remain usable at phone width | Summary and coverage stack; matrix uses a 332 px viewport over a 720 px horizontally scrollable grid; detail becomes one column | Passed |
| Accessibility | Keyboard and non-color operation | Populated cells are native buttons with grid roles, labels, pressed state, visible focus, and focus return on close | Passed |

## Findings

- P0: none.
- P1: none.
- P2: none.
- P3: none requiring a product change. The mobile full-page browser capture showed a stitching seam around the horizontally scrollable matrix; live layout metrics and interaction confirmed the component itself remains continuous and scrollable.

## Final result

`passed`

The implementation matches the supplied visual direction while retaining EDGE 2.0 typography, spacing, color tokens, and the existing current-location section. No unrelated redesign was introduced.
