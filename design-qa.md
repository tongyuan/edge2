# EDGE 2.0 combined UI update — visual QA

Date: 2026-11-09

## References

- Taxonomy ranking reference: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-1aff229b-58e5-4fbd-8030-1bccea27857a.png`
- Watchlists navigation reference: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-21ed918f-2053-4339-908a-f266421eb354.png`
- Contributor-filter removal reference: `/var/folders/dm/ctz4b4_d2yq9jbskg25nx6xw0000gn/T/codex-clipboard-88d2acef-8170-4c02-8d8c-73481e22f3dd.png`
- Implementation verified in the Codex in-app browser at the local Location Distribution route with the 20D, Sector, Financials, Deep Discount → Shallow Discount state.

## Data and interaction validation

- Default `Most Symbols Moving Lower` ranking showed Technology, Financials, then Communication Services for the verified 20D data.
- `Highest % Moving Lower` showed Financials, Communication Services, then Technology.
- Verified all five sort choices, count-and-percentage labels, taxonomy and transition selection persistence, and exact contributor membership.
- The selected Deep Discount → Shallow Discount flow showed OWL and ZION after the filter control was removed.
- The sidebar and page identity display `Watchlists`; underlying route and API contracts remain unchanged.
- The contributor filter is absent from the DOM and visible page text; contributor detail links remain available.
- Browser console: no errors or warnings.

## Responsive validation

- Desktop: 1440 × 1000.
- Mobile: 390 × 844.
- Mobile document width: 390 px client width and 390 px scroll width, with no page-level horizontal overflow.
- The existing flow canvas remains contained in its horizontally scrollable region and contributor rows retain their compact mobile presentation.

## Findings

- P0: none.
- P1: none.
- P2: none.

## Result

passed
