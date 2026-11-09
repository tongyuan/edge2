# Location Distribution redesign — visual QA

Date: 2026-11-09

## Reference fidelity

- Compared against the three approved dark-interface references supplied with the task.
- Preserved the reference hierarchy: page identity and coverage first, compact taxonomy cards second, endpoint bucket flow third, contributing symbols last.
- Matched the reference visual language with narrow centered content, restrained dark surfaces, red/gray/green factual movement encoding, compact typography, and selected-card treatment.
- Used the existing EDGE shell, spacing tokens, controls, and navigation rather than introducing a parallel design system.

## Data and interaction validation

- Validated locally with read-only current `/api/symbols` data and all three canonical history windows.
- 5D coverage displayed 133 eligible, 132 comparable, 125 with new observations, 7 without new observations, and 1 unavailable/incomparable.
- Verified taxonomy level changes (Sector, Industry, Asset Class), With Movement / All Taxonomies, all sort modes, taxonomy selection, window changes, persistent URL state, flow selection, exact contributor membership, contributor search, and symbol detail links.
- Verified flow widths use transition counts and flow colors use the canonical endpoint direction returned by the backend.
- Browser console: no errors or warnings.

## Responsive validation

- Desktop: 1440 × 1000.
- Mobile: 390 × 844.
- Document width at mobile: 390 px client width and 390 px scroll width (no page-level horizontal overflow).
- The fixed-width flow canvas remains contained in its own horizontally scrollable region.
- Contributor rows convert from a compact table to labeled stacked cards on small screens.

## Result

Passed. The implementation is ready for operator review. It has not been deployed.
