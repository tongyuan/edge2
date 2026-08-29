from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from psycopg2.extras import RealDictCursor

from app.db import connect, transaction
from app.domain import ActiveMRZ, MRZEventType, MRZTransition, Observation, ReplayResult
from app.repository import EdgeRepository, active_from_row, observation_from_row
from app.state_engine import replay_symbol
from app.validation import normalize_symbol


RESULT_NO_CHANGE = "NO CHANGE"
RESULT_RECONCILIATION_REQUIRED = "RECONCILIATION REQUIRED"


@dataclass(frozen=True, slots=True)
class PersistedDerivedState:
    symbol: str
    observations: tuple[Observation, ...]
    active_mrz: ActiveMRZ
    events: tuple[Mapping[str, Any], ...]


class ReconciliationError(RuntimeError):
    pass


class ReconciliationPlanChanged(ReconciliationError):
    pass


class DerivedStateReconciler:
    """Manually compare or rebuild derived MRZ state from canonical observations."""

    def __init__(
        self,
        database_url: str,
        *,
        repository: EdgeRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_url = database_url
        self.repository = repository or EdgeRepository(database_url)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def dry_run(self, symbols: Sequence[str] | None = None) -> dict[str, Any]:
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                reports = self._build_reports(cursor, symbols)
            connection.commit()
        finally:
            connection.close()
        return self._report_payload("DRY_RUN", reports)

    def apply(
        self,
        symbols: Sequence[str] | None = None,
        *,
        expected_plan_digest: str | None = None,
    ) -> dict[str, Any]:
        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                symbol_names = self._symbol_names(cursor, symbols)
                for symbol in symbol_names:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (symbol,),
                    )
                reports = self._build_reports(cursor, symbol_names)
                plan_digest = reconciliation_plan_digest(reports)
                if (
                    expected_plan_digest is not None
                    and expected_plan_digest != plan_digest
                ):
                    raise ReconciliationPlanChanged(
                        "Reconciliation plan changed; run a new dry run before apply"
                    )

                applied_symbols: list[str] = []
                for report in reports:
                    if report["result"] == RESULT_NO_CHANGE:
                        continue
                    snapshot = self._read_symbol(cursor, report["symbol"])
                    replay = replay_symbol(snapshot.observations)
                    try:
                        self.repository._replace_derived_state(cursor, replay)
                    except Exception as exc:
                        raise ReconciliationError(
                            f"Failed to persist derived state for {snapshot.symbol}: {exc}"
                        ) from exc
                    applied_symbols.append(snapshot.symbol)

                verified_reports = self._build_reports(cursor, symbol_names)
                unresolved = [
                    report["symbol"]
                    for report in verified_reports
                    if report["result"] != RESULT_NO_CHANGE
                ]
                if unresolved:
                    raise ReconciliationError(
                        "Post-apply verification failed for: " + ", ".join(unresolved)
                    )

        return {
            "mode": "APPLY",
            "generated_at": iso(self.clock()),
            "plan_digest": plan_digest,
            "applied_symbol_count": len(applied_symbols),
            "applied_symbols": applied_symbols,
            "verified_no_change_count": len(verified_reports),
            "result": "APPLIED" if applied_symbols else "NO CHANGES",
            "symbols": verified_reports,
        }

    def _report_payload(
        self,
        mode: str,
        reports: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        required = [
            report["symbol"]
            for report in reports
            if report["result"] == RESULT_RECONCILIATION_REQUIRED
        ]
        return {
            "mode": mode,
            "generated_at": iso(self.clock()),
            "plan_digest": reconciliation_plan_digest(reports),
            "symbol_count": len(reports),
            "no_change_count": len(reports) - len(required),
            "reconciliation_required_count": len(required),
            "reconciliation_required_symbols": required,
            "result": (
                RESULT_RECONCILIATION_REQUIRED if required else RESULT_NO_CHANGE
            ),
            "symbols": list(reports),
        }

    def _build_reports(
        self,
        cursor: RealDictCursor,
        symbols: Sequence[str] | None,
    ) -> list[dict[str, Any]]:
        return [
            compare_derived_state(snapshot, replay_symbol(snapshot.observations))
            for snapshot in (
                self._read_symbol(cursor, symbol)
                for symbol in self._symbol_names(cursor, symbols)
            )
        ]

    @staticmethod
    def _symbol_names(
        cursor: RealDictCursor,
        symbols: Sequence[str] | None,
    ) -> tuple[str, ...]:
        requested = (
            tuple(sorted({normalize_symbol(symbol) for symbol in symbols}))
            if symbols
            else None
        )
        if requested is None:
            cursor.execute(
                """
                SELECT a.symbol
                FROM active_mrz a
                WHERE EXISTS (
                    SELECT 1 FROM observations o WHERE o.symbol = a.symbol
                )
                ORDER BY a.symbol ASC
                """
            )
        else:
            cursor.execute(
                """
                SELECT a.symbol
                FROM active_mrz a
                WHERE a.symbol = ANY(%s)
                  AND EXISTS (
                      SELECT 1 FROM observations o WHERE o.symbol = a.symbol
                  )
                ORDER BY a.symbol ASC
                """,
                (list(requested),),
            )
        found = tuple(str(row["symbol"]) for row in cursor.fetchall())
        if requested is not None:
            missing = sorted(set(requested) - set(found))
            if missing:
                raise ReconciliationError(
                    "No persisted active MRZ with observations for: "
                    + ", ".join(missing)
                )
        return found

    @staticmethod
    def _read_symbol(cursor: RealDictCursor, symbol: str) -> PersistedDerivedState:
        cursor.execute(
            """
            SELECT * FROM observations
            WHERE symbol = %s
            ORDER BY observed_at ASC, received_at ASC, id ASC
            """,
            (symbol,),
        )
        observations = tuple(observation_from_row(row) for row in cursor.fetchall())
        cursor.execute("SELECT * FROM active_mrz WHERE symbol = %s", (symbol,))
        active = active_from_row(cursor.fetchone())
        if active is None or not observations:
            raise ReconciliationError(
                f"Reconciliation scope became unavailable for {symbol}"
            )
        cursor.execute(
            "SELECT * FROM mrz_events WHERE symbol = %s ORDER BY sequence ASC",
            (symbol,),
        )
        events = tuple(dict(row) for row in cursor.fetchall())
        return PersistedDerivedState(symbol, observations, active, events)


def compare_derived_state(
    persisted: PersistedDerivedState,
    replay: ReplayResult,
) -> dict[str, Any]:
    replay_active = replay.active_mrz
    expected_events = {
        transition.event_key: transition_signature(transition)
        for transition in replay.transitions
    }
    persisted_events = {
        str(row["event_key"]): persisted_event_signature(row)
        for row in persisted.events
    }
    missing_event_keys = sorted(set(expected_events) - set(persisted_events))
    removed_event_keys = sorted(set(persisted_events) - set(expected_events))
    changed_event_keys = sorted(
        event_key
        for event_key in set(expected_events) & set(persisted_events)
        if expected_events[event_key] != persisted_events[event_key]
    )
    active_changed = replay_active != persisted.active_mrz
    authority_changes = (
        authority_signature(replay_active)
        != authority_signature(persisted.active_mrz)
    )
    requires_reconciliation = bool(
        active_changed
        or missing_event_keys
        or removed_event_keys
        or changed_event_keys
    )
    expected_migrations = tuple(
        transition
        for transition in replay.transitions
        if transition.event_type is MRZEventType.MIGRATED
    )
    persisted_migrations = tuple(
        row
        for row in persisted.events
        if str(row["event_type"]) == MRZEventType.MIGRATED.value
    )
    missing_migrations = sum(
        transition.event_key in missing_event_keys
        for transition in expected_migrations
    )
    return {
        "symbol": persisted.symbol,
        "persisted_active_mrz": active_payload(persisted.active_mrz),
        "replay_active_mrz": active_payload(replay_active),
        "authority_changes": authority_changes,
        "derived_active_state_changes": active_changed,
        "persisted_migration_event_count": len(persisted_migrations),
        "replay_migration_event_count": len(expected_migrations),
        "missing_historical_migrations": missing_migrations,
        "missing_event_keys": missing_event_keys,
        "removed_event_keys": removed_event_keys,
        "changed_event_keys": changed_event_keys,
        "removed_or_changed_event_count": (
            len(removed_event_keys) + len(changed_event_keys)
        ),
        "final_replay_authority_at": (
            iso(replay_active.activated_at) if replay_active else None
        ),
        "reconstructed_mrz_path": reconstructed_path(replay.transitions),
        "result": (
            RESULT_RECONCILIATION_REQUIRED
            if requires_reconciliation
            else RESULT_NO_CHANGE
        ),
    }


def active_payload(active: ActiveMRZ | None) -> dict[str, Any] | None:
    if active is None:
        return None
    return {
        "route_owner": active.route_owner.value,
        "core_mrz_lower": decimal_text(active.core_mrz_lower),
        "core_mrz_upper": decimal_text(active.core_mrz_upper),
        "core_mrz_midpoint": decimal_text(active.core_mrz_midpoint),
        "structural_location": active.structural_location.value,
        "confirming_observation_count": active.confirming_observation_count,
        "supporting_observation_count": active.supporting_observation_count,
        "activated_at": iso(active.activated_at),
        "activation_event_id": active.activation_event_id,
        "formation_started_at": iso(active.formation_started_at),
        "formation_completed_at": iso(active.formation_completed_at),
        "formation_duration_seconds": decimal_text(active.formation_duration_seconds),
        "ipda_20w_high_at_activation": decimal_text(
            active.ipda_20w_high_at_activation
        ),
        "ipda_20w_low_at_activation": decimal_text(
            active.ipda_20w_low_at_activation
        ),
        "ipda_width_at_activation": decimal_text(active.ipda_width_at_activation),
        "normalized_span_at_activation": decimal_text(
            active.normalized_span_at_activation
        ),
        "instrument_tick": decimal_text(active.instrument_tick),
    }


def authority_signature(active: ActiveMRZ | None) -> tuple[Any, ...] | None:
    if active is None:
        return None
    return (
        active.route_owner,
        active.core_mrz_lower,
        active.core_mrz_upper,
        active.core_mrz_midpoint,
        active.structural_location,
        active.activated_at,
        active.activation_event_id,
    )


def reconstructed_path(
    transitions: Sequence[MRZTransition],
) -> list[dict[str, Any]]:
    return [
        {
            "event_type": transition.event_type.value,
            "route_owner": transition.new_mrz.route_owner.value,
            "core_mrz_lower": decimal_text(transition.new_mrz.core_mrz_lower),
            "core_mrz_upper": decimal_text(transition.new_mrz.core_mrz_upper),
            "structural_location": transition.new_mrz.structural_location.value,
            "occurred_at": iso(transition.occurred_at),
            "trigger_event_id": transition.trigger_event_id,
        }
        for transition in transitions
        if transition.event_type in {MRZEventType.ACTIVATED, MRZEventType.MIGRATED}
    ]


def transition_signature(transition: MRZTransition) -> dict[str, Any]:
    old = transition.old_mrz
    new = transition.new_mrz
    return {
        "event_key": transition.event_key,
        "sequence": transition.sequence,
        "event_type": transition.event_type.value,
        "symbol": transition.symbol,
        "route_owner": transition.route_owner.value,
        "previous_route_owner": (
            transition.previous_route_owner.value
            if transition.previous_route_owner
            else None
        ),
        "occurred_at": transition.occurred_at,
        "trigger_event_id": transition.trigger_event_id,
        "old_core_mrz_lower": old.core_mrz_lower if old else None,
        "old_core_mrz_upper": old.core_mrz_upper if old else None,
        "new_core_mrz_lower": new.core_mrz_lower,
        "new_core_mrz_upper": new.core_mrz_upper,
        "new_core_mrz_midpoint": new.core_mrz_midpoint,
        "structural_location": new.structural_location.value,
        "confirming_observation_count": new.confirming_observation_count,
        "old_supporting_observation_count": (
            old.supporting_observation_count if old else None
        ),
        "new_supporting_observation_count": new.supporting_observation_count,
        "old_formation_started_at": old.formation_started_at if old else None,
        "old_formation_completed_at": old.formation_completed_at if old else None,
        "old_formation_duration_seconds": (
            old.formation_duration_seconds if old else None
        ),
        "new_formation_started_at": new.formation_started_at,
        "new_formation_completed_at": new.formation_completed_at,
        "new_formation_duration_seconds": new.formation_duration_seconds,
        "details": transition.details,
    }


def persisted_event_signature(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "event_key",
        "sequence",
        "event_type",
        "symbol",
        "route_owner",
        "previous_route_owner",
        "occurred_at",
        "trigger_event_id",
        "old_core_mrz_lower",
        "old_core_mrz_upper",
        "new_core_mrz_lower",
        "new_core_mrz_upper",
        "new_core_mrz_midpoint",
        "structural_location",
        "confirming_observation_count",
        "old_supporting_observation_count",
        "new_supporting_observation_count",
        "old_formation_started_at",
        "old_formation_completed_at",
        "old_formation_duration_seconds",
        "new_formation_started_at",
        "new_formation_completed_at",
        "new_formation_duration_seconds",
        "details",
    )
    return {key: row.get(key) for key in keys}


def reconciliation_plan_digest(reports: Sequence[Mapping[str, Any]]) -> str:
    serialized = json.dumps(
        list(reports),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")
