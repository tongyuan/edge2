# EDGE 2.0 — MRZ Migration Path Validation & Functional Remediation

Date: 2026-11-22
Environment: local `edge2-app` + local PostgreSQL container `edge2-db`
Database: `edge2_radar`, schema migrations `001`–`022`
Safety: read-only canonical audit; no production access, deployment, push or production-data mutation

## Verdict

**GO WITH CONDITIONS**

The path component, canonical state mapping, selected evidence, viewport controls, docking, maximize/restore, responsive behavior and empty/limited states are working locally. The local database does not contain a mature real migration history, so dense rendering and structural annotations were tested with a clearly labelled disposable fixture outside PostgreSQL. Full production-data readiness cannot be established from that fixture.

## A. Data availability

| Migration category | Symbols |
|---|---:|
| 0 migrations | 19 |
| 1–3 migrations | 4 |
| 4–9 migrations | 0 |
| 10+ migrations | 0 |

Every symbol currently has an active MRZ. Structural eligibility requires enough canonical states for the shared detector; none of the local symbols qualifies.

| Symbol | Migration events | Distinct MRZ states | Migration coverage | Active MRZ | Structural eligibility | Scenario |
|---|---:|---:|---|---|---|---|
| 9988.HK | 1 | 2 | 09 Nov 2026 | BTD 132.0–132.6 | Insufficient | Limited |
| AAPL | 1 | 2 | 09 Nov 2026 | BTD 125.0–125.6 | Insufficient | Limited |
| BTCUSDT | 1 | 2 | 09 Nov 2026 | BTD 135.0–135.6 | Insufficient | **Limited acceptance case** |
| SMH | 1 | 2 | 09 Nov 2026 | STR 170.0–170.6 | Insufficient | Limited |
| 0700.HK | 0 | 1 | No migrations | BTD 111.0–111.6 | Insufficient | **Zero-history acceptance case** |
| ETHUSDT | 0 | 1 | No migrations | STR 181.0–181.6 | Insufficient | Preferred symbol unavailable |
| AMD, AMZN, BAC, BIIB, GOOGL, INTC, JD.HK, JPM, META, MSFT, NIO, NVDA, PFE, SOLUSDT, TSLA, XLF, XPEV | 0 each | 1 each | No migrations | Active | Insufficient | Zero-history |
| FIXTURE-MATURE | 11 | 12 | 01 Sep–26 Oct 2026 | Isolated fixture | Detector exercise only | **Disposable UI/detector fixture** |

### Why 0700.HK shows zero

`0700.HK` is normalized and queried correctly. Its canonical event history contains one `MRZ_ACTIVATED` event and no `MRZ_MIGRATED` event. The history API returns an empty migration array. This is a data-availability fact, not a symbol-normalization or query defect.

### ETHUSDT finding

ETHUSDT's local history contains only its activation at 181.0–181.6 STR. The approximately 14 migrations shown in earlier operator screenshots are not present in this local database. The database has only 28 MRZ events in total: 23 activations, four migrations and one route change. The gap is local database completeness/source identity, not frontend filtering.

## B. Migration Path implementation

Reviewed `EdgeRepository.symbol_inspection_history`, both symbol history APIs, Symbol Workspace loading, structural summaries, `migration-path.js`, shared viewport helpers, docking and responsive CSS.

Corrections:

1. History returns the complete canonical state chain: activation plus migration states.
2. Migration-event count remains separate from distinct state count.
3. Each state includes event time, first-known time, route, bounds, midpoint, canonical identity and evidence reference.
4. Generate Path is a read-only projection of authoritative history; it creates no events and is repeatable.
5. Zero-history symbols show an explicit explanation and cannot fabricate a path.
6. Selected evidence is visible and reconciles with the selected chart state.
7. Pinch, pointer drag, horizontal wheel, toolbar zoom, reset, Earlier/Newer, maximize and docking share bounded viewport state.
8. Dock and Undock preserve symbol, selected canonical event, window start and window size.
9. Expanded and docked canvases redraw at their real dimensions instead of stretching.
10. Active symbols use the approved green `● MRZ ACTIVE` header pill.

## C. Structural validation

### Real local history

- BTCUSDT: two states, downward midpoint change 149.3 → 135.3, `Undetermined`, `Unresolved`, insufficient evidence, no HH/HL/LH/LL annotation.
- ETHUSDT: one activation state, `Undetermined`, `Unresolved`, insufficient evidence. The local dataset cannot reproduce the prior descending-history/active-BTD regression case.
- 0700.HK: one activation state, no structural conclusion.

### Isolated detector fixture

The SI-1.0.0 detector received 12 timestamped states and returned `Transitional / Unresolved / Developing`. Confirmed pivots were HIGH, LOW, HH, HL, HH, LL, LH, LL, LH and LL; the final LH remained developing. Confirmation times use the later confirming state's first-known time. This fixture proves rendering and detector integration, not production-data accuracy.

Automated regression coverage confirms that knowledge cutoffs exclude future-known states, one opposite migration does not establish a reversal, and active route alone does not determine the route hypothesis.

## D. Chart interaction matrix

| Interaction | Result | Evidence |
|---|---|---|
| Pan via Earlier/Newer | PASS | Browser: states #7–#10 → #4–#7 |
| Mouse drag pan | NOT TESTED | Handler present; browser control could not synthesize position-specific canvas drag |
| Trackpad horizontal scroll | NOT TESTED | Handler present; gesture synthesis unavailable |
| Zoom In | PASS | Browser: six visible states → four |
| Zoom Out | PASS | Automated viewport test + browser reset cycle |
| Reset View | PASS | Restored latest six states and hid transient evidence overlay |
| Earlier/Newer bounds | PASS | Disabled correctly at history edges |
| All / 90D / 30D | NOT APPLICABLE | These presets belong to Opportunity Map; Migration Path uses state windows |
| Dock | PASS | Real popup opened with symbol, viewport and selected event in URL |
| Undock | PASS | Restored main Symbol Workspace with the same viewport and event |
| Resize | PASS | Canvas redrew 1710×744 → 716×408 |
| Maximize | PASS | Browser-verified 1710×704 backing canvas |
| Restore | PASS | Original panel class and viewport restored |
| Selected-point evidence | PASS | Identity, times, bounds, midpoint, route and canonical reference visible |
| Keyboard navigation | PASS | Arrow selection exposed the previous canonical state |
| Touch layout | PASS | iPad/iPhone layouts had no document overflow |
| Touch drag / pinch | NOT TESTED | Implemented; direct multi-touch synthesis unavailable |

## E. Visual evidence

1. `artifacts/mrz-fixture-mature-initial.jpg` — populated fixture, clearly marked non-canonical.
2. `artifacts/mrz-fixture-zoomed.jpg` — zoomed fixture.
3. `artifacts/mrz-fixture-panned.jpg` — panned fixture with selected evidence.
4. `artifacts/mrz-fixture-maximized.jpg` — maximized fixture.
5. `artifacts/mrz-docked-btcusdt.jpg` — docked real BTCUSDT chart.
6. `artifacts/mrz-limited-btcusdt.jpg` — limited real BTCUSDT chart.
7. `artifacts/mrz-zero-0700hk.jpg` — zero-history real 0700.HK.
8. `artifacts/mrz-active-badge-ethusdt.jpg` — approved active-state header.
9. `artifacts/mrz-ipad-btcusdt.jpg`, `artifacts/mrz-iphone-btcusdt.jpg` — responsive checks.

## Files changed

- `app/repository.py`
- `app/static/index.html`
- `app/static/workspace.js`
- `app/static/migration-path.js`
- `app/static/docking.js`
- `app/static/workspace.css`
- `tests/test_api.py`
- `tests/test_migration_path.js`
- `tests/test_docking.js`
- cache-version expectations in contract tests
- local-only fixture and screenshots under `artifacts/`

## Automated verification

- Full local non-Pine suite: **541 passed, 8 skipped, 0 failed**.
- JavaScript migration-path and docking tests passed within that suite.
- Blank chart taps dismiss selected-state evidence, short-history zoom changes the price scale, and the docked view excludes Hide Path and parent-workspace Event History.
- Production, production data and the remote repository were not changed.

## Remaining conditions

1. Validate at least one authorized real symbol with four or more migrations, preferably the earlier ETHUSDT history.
2. Repeat the dense browser matrix against that real canonical chain.
3. Perform physical trackpad and touch pinch/drag checks on operator devices.
4. Only then consider a production deployment approval.
