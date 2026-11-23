# EDGE 2.0 — Structural Development Notification Readiness Report

Date: 23 November 2026
Scope: implementation, validation and operator-approved production release
Production status: pre-deployment safety gates complete; deployment in progress

## Executive verdicts

| Decision | Verdict | Basis |
|---|---|---|
| Retire legacy Structural Transition notifications and review authority | **GO for an operator-approved release** | Active delivery, unread counts, Inbox actions and review mutation are retired. Historical transition records remain available for audit and rollback. |
| Activate Structural Development as a selectable notification type | **GO** | Detector, delivery, preference, deduplication, activation-boundary and deep-link tests pass. Production identity, backup integrity and isolated restore verification were completed before deployment. |
| Overall production release | **GO — operator approved** | The code and production safety gates are ready; post-deploy health, release-boundary and notification-preference verification remain required. |

## 1. Legacy Structural Transition audit and retirement

The legacy feature was distributed across the transition tables introduced by migrations 020/021, repository transition reconciliation, the transition review endpoint, notification outbox categories, Inbox queries, unread counts and browser push handling.

The release now:

- rejects the retired operator transition-review mutation;
- removes legacy Structural Transition items from the active Inbox, unread counts, delivery queues and bulk Inbox actions;
- prevents the service worker from presenting a legacy Structural Transition push;
- retains historical transition rows and labels them as legacy evidence in event history;
- leaves the old schema and dormant reconciliation method in place for evidence preservation and safe rollback;
- does not reinterpret an opposite-route MRZ activation as a Structural Development.

No legacy notification preference is copied into the new Structural Development preference.

## 2. Structural Development detector readiness

Detector version: `SI-1.0.0`.

The detector continues to use canonical MRZ activation/migration history and instrument precision. Its alert identity distinguishes developing and confirmed lifecycle stages. Confirmation knowledge time is now the confirmation state's first-known time, preventing an earlier pivot timestamp from crossing the release boundary.

Validated locally:

- developing higher-low and lower-high developments;
- confirmed higher-high, higher-low, lower-high and lower-low developments;
- stable event identity and idempotent reconciliation;
- chronological knowledge-time handling;
- no alert from an opposite-route activation alone;
- no automatic promotion of a route hypothesis;
- no change to canonical MRZ, migration, Near Miss or structural calculations.

Limitation: the release does not invent a notification solely from a broad structural-classification label change. A notification requires a qualifying canonical structural development produced by the detector.

## 3. Preference and activation controls

Migration `023_structural_development_alert_release.sql` adds an explicit release record and a per-operator activation boundary.

Behavior after an approved migration:

- Structural Development becomes selectable only when the release record is available and its detector version matches the running detector;
- the preference remains off by default;
- enabling records `structural_development_enabled_at`;
- disabling clears that activation time;
- re-enabling starts a new activation boundary;
- tracked-groups/all-symbols scope and device subscription enablement continue to apply;
- events created before the operator enables the preference remain out of the active Inbox and push queue;
- historical or pre-release detector rows remain shadow-only and cannot create a backfill flood.

The release is seeded with its deployment-time boundary only when migration 023 is actually applied. It is not active in production now.

## 4. Notification identity, content and evidence links

Structural Development notifications use stable development identity with database uniqueness and idempotent outbox reconciliation. Titles distinguish emerging accumulation/distribution from confirmed higher-high, higher-low, lower-high and lower-low developments.

Deep links open the existing Symbol Workspace with the MRZ Migration Path focused on the development's canonical pivot. The details include the supporting migration event keys. No parallel evidence page was introduced.

## 5. Validation matrix

| Area | Result | Evidence |
|---|---|---|
| Legacy transition delivery retirement | PASS | Legacy type excluded from active delivery and service-worker presentation. |
| Legacy transition Inbox/unread retirement | PASS | Active list, counts and bulk actions exclude the legacy type. |
| Historical transition preservation | PASS | Legacy records remain visible as historical audit evidence. |
| Legacy review authority retirement | PASS | Review mutation returns the retired/conflict response. |
| MRZ Activation regression | PASS | Existing notification integration suite passes. |
| MRZ Migration regression | PASS | Existing notification integration suite passes. |
| Near Miss regression | PASS | Existing notification integration suite passes. |
| Developing HL/LH | PASS | Detector and integration coverage pass. |
| Confirmed HH/HL/LH/LL | PASS | Detector and integration coverage pass. |
| Knowledge-time safety | PASS | Confirmation uses confirmation-state first-known time. |
| Release boundary | PASS | Pre-release developments remain shadow-only. |
| Preference activation boundary | PASS | Enabling does not release pre-enable backlog; subsequent eligible events can deliver. |
| Duplicate/retry safety | PASS | Stable identity plus unique reconciliation remains idempotent. |
| Scope and device controls | PASS | Existing tracked/all-symbol scope and device enablement are preserved. |
| Inbox rendering and unread counts | PASS | Current types render; legacy type is excluded. |
| Canonical deep link | PASS | Symbol Workspace opens with Migration Path and pivot evidence selected. |
| Browser safety | PASS | Updated scripts parse; unsupported legacy push is ignored. |
| Production backup integrity | PASS | Fresh custom-format backup verified by checksum, non-zero size, mode 600 and 246 readable catalog entries. |
| Production restore rehearsal | PASS | Fresh backup restored into an isolated disposable database; 22 migrations, 6,692 observations and 79 active MRZ rows verified before cleanup. |

## 6. Test results

- Full local regression: **558 tests passed; 8 intentionally skipped retired Pressure tests**.
- Python compile validation: passed.
- Browser script syntax validation: passed.
- Patch whitespace validation: passed.

The local database-backed test environment was created and removed for the suite. Production was contacted only for the approved identity, backup and isolated restore checks before deployment.

## 7. Files changed

Application and release control:

- `migrations/023_structural_development_alert_release.sql`
- `app/structural_intelligence.py`
- `app/repository.py`
- `app/notifications.py`
- `app/api.py`
- `app/group_evidence.py`

Interface and browser delivery:

- `app/static/index.html`
- `app/static/workspace.js`
- `app/static/migration-path.js`
- `app/static/notifications.js`
- `app/static/service-worker.js`

Validation:

- `tests/db_support.py`
- `tests/test_notifications.py`
- `tests/test_notifications.js`
- `tests/test_structural_intelligence.py`
- `tests/test_structural_transitions.py`
- `tests/test_workspace_contract.py`

## 8. Production release safeguards

The operator approved the deployment and Structural Development notification activation. The release procedure must preserve this order:

1. Verify the intended EDGE 2.0/SPCX production host, application identity, database identity and release commit.
2. Create a fresh production database backup outside the Git repository and verify its checksum and readable contents.
3. Restore that backup into an isolated disposable database and run a restore smoke test.
4. Rehearse migration 023 and the rollback procedure against the restored copy.
5. Deploy with Structural Development initially disabled for every operator.
6. Confirm the release record, detector version, live boundary, Inbox counts and absence of historical backfill.
7. Observe shadow/event reconciliation before an operator explicitly enables the new preference.
8. Enable only after the operator reviews the production evidence and approves activation. Approval was received on 23 November 2026.

Backups must not be committed to GitHub. They should be encrypted and retained in the approved production backup location with restricted access.

## 9. Rollback plan

If the release fails validation:

1. Set the Structural Development release record unavailable and turn the preference off for all operators.
2. Redeploy the prior application release.
3. Leave the additive migration 023 table/column in place unless a separately reviewed database rollback is necessary; this avoids destructive rollback risk.
4. Preserve structural developments, legacy transitions and notification history as audit evidence.
5. Verify MRZ Activation, MRZ Migration and Near Miss delivery after rollback.

This rollback does not require deleting canonical events or historical notification records.
