from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from psycopg2 import errors
from psycopg2.extras import Json, RealDictCursor

from app.activation_feasibility import current_production_near_misses
from app.concentration import (
    CONCENTRATION_SPAN_THRESHOLD,
    ROUTE_OBSERVATION_WINDOW,
    ConcentrationDiagnostic,
    ConcentrationResult,
    evaluate_concentration,
)
from app.db import connect, transaction
from app.domain import (
    ActivationSource,
    ActiveMRZ,
    Cluster,
    MRZTransition,
    Observation,
    ObservationType,
    ReplayResult,
    Route,
    StructuralLocation,
)
from app.group_tracking import SavedGroupNameConflict
from app.state_engine import effective_instrument_tick, replay_symbol
from app.structure import (
    classify_ipda_location,
    classify_structural_location,
    ipda_directional_context,
)
from app.validation import ObservationPayload, normalize_symbol


LOGGER = logging.getLogger("edge2.repository")

LOCATION_MIGRATION_KEYS = {
    StructuralLocation.DEEP_DISCOUNT.value: "deep_discount",
    StructuralLocation.SHALLOW_DISCOUNT.value: "shallow_discount",
    StructuralLocation.SHALLOW_PREMIUM.value: "shallow_premium",
    StructuralLocation.DEEP_PREMIUM.value: "deep_premium",
}
GROUP_LOCATION_KEYS = (
    "deep_discount",
    "shallow_discount",
    "shallow_premium",
    "deep_premium",
)
STRUCTURAL_LOCATION_PRESENTATION = {
    StructuralLocation.DEEP_DISCOUNT.value: ("DD", "Deep Discount"),
    StructuralLocation.SHALLOW_DISCOUNT.value: ("SD", "Shallow Discount"),
    StructuralLocation.SHALLOW_PREMIUM.value: ("SP", "Shallow Premium"),
    StructuralLocation.DEEP_PREMIUM.value: ("DP", "Deep Premium"),
}


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    accepted: bool
    duplicate: bool
    event_id: str
    symbol: str
    replay: ReplayResult | None
    triggered_transitions: tuple[MRZTransition, ...]


@dataclass(frozen=True, slots=True)
class PromotionOutcome:
    symbol: str
    route: Route
    candidate_identity: str
    duplicate: bool
    trigger_event_id: str


class PromotionConflict(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def location_migration_tendency_payload(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, int | float | None]]:
    result: dict[str, dict[str, int | float | None]] = {
        key: {
            "migration_samples": 0,
            "higher_count": 0,
            "lower_count": 0,
            "higher_pct": None,
            "lower_pct": None,
        }
        for key in LOCATION_MIGRATION_KEYS.values()
    }
    for row in rows:
        structural_location = str(row["starting_structural_location"])
        key = LOCATION_MIGRATION_KEYS.get(structural_location)
        if key is None:
            raise ValueError(
                f"Unknown authoritative MRZ structural location: {structural_location}"
            )
        equal_count = int(row["equal_count"])
        if equal_count:
            raise ValueError(
                "Authoritative MRZ migration history contains equal old/new midpoints"
            )
        higher_count = int(row["higher_count"])
        lower_count = int(row["lower_count"])
        migration_samples = higher_count + lower_count
        result[key] = {
            "migration_samples": migration_samples,
            "higher_count": higher_count,
            "lower_count": lower_count,
            "higher_pct": (
                (higher_count / migration_samples) * 100
                if migration_samples
                else None
            ),
            "lower_pct": (
                (lower_count / migration_samples) * 100
                if migration_samples
                else None
            ),
        }
    return result


def observation_from_row(row: Mapping[str, Any]) -> Observation:
    return Observation(
        id=int(row["id"]),
        event_id=str(row["event_id"]),
        schema_version=str(row["schema_version"]),
        symbol=str(row["symbol"]),
        route=Route(str(row["route"])),
        observation_type=ObservationType(str(row["observation_type"])),
        observation_price=Decimal(row["observation_price"]),
        observation_price_tick=Decimal(row["observation_price_tick"]),
        ipda_20w_high=Decimal(row["ipda_20w_high"]),
        ipda_20w_low=Decimal(row["ipda_20w_low"]),
        observed_at=row["observed_at"],
        received_at=row["received_at"],
    )


def active_from_row(row: Mapping[str, Any] | None) -> ActiveMRZ | None:
    if not row:
        return None
    return ActiveMRZ(
        symbol=str(row["symbol"]),
        route_owner=Route(str(row["route_owner"])),
        core_mrz_lower=Decimal(row["core_mrz_lower"]),
        core_mrz_upper=Decimal(row["core_mrz_upper"]),
        core_mrz_midpoint=Decimal(row["core_mrz_midpoint"]),
        structural_location=StructuralLocation(str(row["structural_location"])),
        confirming_observation_count=int(row["confirming_observation_count"]),
        supporting_observation_count=int(row["supporting_observation_count"]),
        activated_at=row["activated_at"],
        activation_event_id=str(row["activation_event_id"]),
        formation_started_at=row.get("formation_started_at"),
        formation_completed_at=row.get("formation_completed_at"),
        formation_duration_seconds=(
            Decimal(row["formation_duration_seconds"])
            if row.get("formation_duration_seconds") is not None
            else None
        ),
        ipda_20w_high_at_activation=Decimal(row["ipda_20w_high_at_activation"]),
        ipda_20w_low_at_activation=Decimal(row["ipda_20w_low_at_activation"]),
        ipda_width_at_activation=Decimal(row["ipda_width_at_activation"]),
        normalized_span_at_activation=Decimal(row["normalized_span_at_activation"]),
        instrument_tick=Decimal(row["instrument_tick"]),
        activation_source=ActivationSource(
            str(row.get("activation_source") or "PRODUCTION_QUALIFIED")
        ),
    )


def promoted_active_from_row(row: Mapping[str, Any] | None) -> ActiveMRZ | None:
    if not row:
        return None
    return ActiveMRZ(
        symbol=str(row["symbol"]),
        route_owner=Route(str(row["route_owner"])),
        core_mrz_lower=Decimal(row["candidate_lower"]),
        core_mrz_upper=Decimal(row["candidate_upper"]),
        core_mrz_midpoint=Decimal(row["candidate_midpoint"]),
        structural_location=StructuralLocation(str(row["structural_location"])),
        confirming_observation_count=int(row["supporting_observation_count"]),
        supporting_observation_count=int(row["supporting_observation_count"]),
        activated_at=row["promoted_at"],
        activation_event_id=str(row["trigger_event_id"]),
        formation_started_at=row["formation_started_at"],
        formation_completed_at=row["formation_completed_at"],
        formation_duration_seconds=Decimal(row["formation_duration_seconds"]),
        ipda_20w_high_at_activation=Decimal(row["ipda_20w_high"]),
        ipda_20w_low_at_activation=Decimal(row["ipda_20w_low"]),
        ipda_width_at_activation=Decimal(row["ipda_width"]),
        normalized_span_at_activation=Decimal(row["normalized_span"]),
        instrument_tick=Decimal(row["instrument_tick"]),
        activation_source=ActivationSource.OPERATOR_PROMOTED,
    )


def migration_provenance_payload(
    row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not row:
        return {"has_migrated": False}
    previous_midpoint = (
        Decimal(row["old_core_mrz_lower"])
        + Decimal(row["old_core_mrz_upper"])
    ) / Decimal("2")
    current_midpoint = Decimal(row["new_core_mrz_midpoint"])
    direction = "UP" if current_midpoint > previous_midpoint else "DOWN"
    return {
        "has_migrated": True,
        "direction": direction,
        "migrated_at": iso(row["occurred_at"]),
        "previous_activated_at": iso(row.get("previous_activated_at")),
        "previous_lower": number(row["old_core_mrz_lower"]),
        "previous_upper": number(row["old_core_mrz_upper"]),
        "current_lower": number(row["new_core_mrz_lower"]),
        "current_upper": number(row["new_core_mrz_upper"]),
        "route_owner": str(row["route_owner"]),
        "migration_event_id": str(row["trigger_event_id"]),
    }


def current_migration_provenance(
    cursor: RealDictCursor,
    active: ActiveMRZ | None,
) -> dict[str, Any]:
    if active is None:
        return migration_provenance_payload(None)
    cursor.execute(
        """
        SELECT
            current_event.occurred_at,
            current_event.trigger_event_id,
            current_event.route_owner,
            current_event.old_core_mrz_lower,
            current_event.old_core_mrz_upper,
            current_event.new_core_mrz_lower,
            current_event.new_core_mrz_upper,
            current_event.new_core_mrz_midpoint,
            previous_authority.occurred_at AS previous_activated_at
        FROM mrz_events current_event
        LEFT JOIN LATERAL (
            SELECT source_event.occurred_at
            FROM mrz_events source_event
            WHERE source_event.symbol = current_event.symbol
              AND source_event.sequence < current_event.sequence
              AND source_event.event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')
              AND source_event.route_owner = current_event.previous_route_owner
              AND source_event.new_core_mrz_lower = current_event.old_core_mrz_lower
              AND source_event.new_core_mrz_upper = current_event.old_core_mrz_upper
              AND source_event.occurred_at <= current_event.occurred_at
            ORDER BY source_event.sequence DESC
            LIMIT 1
        ) previous_authority ON TRUE
        WHERE current_event.symbol = %s
          AND current_event.event_type = 'MRZ_MIGRATED'
          AND current_event.trigger_event_id = %s
          AND current_event.occurred_at = %s
          AND current_event.route_owner = %s
          AND current_event.new_core_mrz_lower = %s
          AND current_event.new_core_mrz_upper = %s
          AND current_event.new_core_mrz_midpoint = %s
        ORDER BY current_event.sequence DESC
        LIMIT 1
        """,
        (
            active.symbol,
            active.activation_event_id,
            active.activated_at,
            active.route_owner.value,
            active.core_mrz_lower,
            active.core_mrz_upper,
            active.core_mrz_midpoint,
        ),
    )
    return migration_provenance_payload(cursor.fetchone())


def concentration_ranking_payload(
    route_windows: Mapping[Route, Sequence[Observation]],
) -> dict[str, Any] | None:
    diagnostics = (
        evaluate_concentration(route_windows[route], route).diagnostic
        for route in Route
    )
    eligible = [
        diagnostic
        for diagnostic in diagnostics
        if (
            diagnostic.retained_observation_count >= diagnostic.minimum_required_count
            and diagnostic.minimum_required_allowance_pct is not None
        )
    ]
    if not eligible:
        return None
    selected = min(
        eligible,
        key=lambda diagnostic: (
            diagnostic.minimum_required_allowance_pct,
            -diagnostic.retained_observation_count,
            diagnostic.route.value,
        ),
    )
    return {
        "route": selected.route.value,
        "observation_count": selected.retained_observation_count,
        "minimum_required_allowance_pct": decimal_text(
            selected.minimum_required_allowance_pct
        ),
        "configured_allowance_pct": decimal_text(selected.configured_allowance_pct),
        "allowance_difference_pct_points": decimal_text(
            selected.allowance_difference_pct_points
        ),
    }


class EdgeRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def ingest(self, payload: ObservationPayload, price_tick: Decimal) -> IngestionOutcome:
        raw_payload = payload.model_dump(mode="json", exclude={"webhook_secret"})
        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (payload.symbol,))
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM active_mrz WHERE symbol = %s) AS active",
                    (payload.symbol,),
                )
                was_active = bool(cursor.fetchone()["active"])
                cursor.execute(
                    """
                    INSERT INTO observations (
                        event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low, observed_at, raw_payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    RETURNING *
                    """,
                    (
                        payload.event_id,
                        payload.schema_version,
                        payload.symbol,
                        payload.route.value,
                        payload.observation_type.value,
                        payload.observation_price,
                        price_tick,
                        payload.ipda_20w_high,
                        payload.ipda_20w_low,
                        payload.observed_at,
                        Json(raw_payload),
                    ),
                )
                inserted = cursor.fetchone()
                if inserted is None:
                    cursor.execute(
                        """
                        UPDATE ingestion_metrics
                        SET duplicate_payload_count = duplicate_payload_count + 1
                        WHERE singleton = TRUE
                        """
                    )
                    return IngestionOutcome(
                        accepted=False,
                        duplicate=True,
                        event_id=payload.event_id,
                        symbol=payload.symbol,
                        replay=None,
                        triggered_transitions=(),
                    )

                cursor.execute(
                    """
                    SELECT * FROM observations
                    WHERE symbol = %s
                    ORDER BY observed_at ASC, received_at ASC, id ASC
                    """,
                    (payload.symbol,),
                )
                symbol_observations = tuple(
                    observation_from_row(row) for row in cursor.fetchall()
                )
                cursor.execute(
                    "SELECT * FROM operator_mrz_promotions WHERE symbol = %s",
                    (payload.symbol,),
                )
                promoted_activation = promoted_active_from_row(cursor.fetchone())
                replay = replay_symbol(
                    symbol_observations,
                    promoted_activation=promoted_activation,
                )
                self._replace_derived_state(cursor, replay)
                self._sync_near_miss_episodes(
                    cursor,
                    symbol=payload.symbol,
                    trigger_event_id=payload.event_id,
                    was_active=was_active,
                )
                cursor.execute(
                    """
                    UPDATE ingestion_metrics
                    SET accepted_payload_count = accepted_payload_count + 1,
                        latest_accepted_webhook_at = %s
                    WHERE singleton = TRUE
                    """,
                    (inserted["received_at"],),
                )
                triggered = tuple(
                    transition
                    for transition in replay.transitions
                    if transition.trigger_event_id == payload.event_id
                )
                return IngestionOutcome(
                    accepted=True,
                    duplicate=False,
                    event_id=payload.event_id,
                    symbol=payload.symbol,
                    replay=replay,
                    triggered_transitions=triggered,
                )

    def _replace_derived_state(self, cursor: RealDictCursor, replay: ReplayResult) -> None:
        cursor.execute("DELETE FROM mrz_events WHERE symbol = %s", (replay.symbol,))
        for transition in replay.transitions:
            old = transition.old_mrz
            new = transition.new_mrz
            cursor.execute(
                """
                INSERT INTO mrz_events (
                    event_key, sequence, event_type, symbol, route_owner,
                    activation_source,
                    previous_route_owner, occurred_at, trigger_event_id,
                    old_core_mrz_lower, old_core_mrz_upper,
                    new_core_mrz_lower, new_core_mrz_upper, new_core_mrz_midpoint,
                    structural_location, confirming_observation_count,
                    old_supporting_observation_count, new_supporting_observation_count,
                    old_formation_started_at, old_formation_completed_at,
                    old_formation_duration_seconds,
                    new_formation_started_at, new_formation_completed_at,
                    new_formation_duration_seconds,
                    details
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    transition.event_key,
                    transition.sequence,
                    transition.event_type.value,
                    transition.symbol,
                    transition.route_owner.value,
                    new.activation_source.value,
                    transition.previous_route_owner.value if transition.previous_route_owner else None,
                    transition.occurred_at,
                    transition.trigger_event_id,
                    old.core_mrz_lower if old else None,
                    old.core_mrz_upper if old else None,
                    new.core_mrz_lower,
                    new.core_mrz_upper,
                    new.core_mrz_midpoint,
                    new.structural_location.value,
                    new.confirming_observation_count,
                    old.supporting_observation_count if old else None,
                    new.supporting_observation_count,
                    old.formation_started_at if old else None,
                    old.formation_completed_at if old else None,
                    old.formation_duration_seconds if old else None,
                    new.formation_started_at,
                    new.formation_completed_at,
                    new.formation_duration_seconds,
                    Json(transition.details),
                ),
            )

        active = replay.active_mrz
        if active is None:
            cursor.execute("DELETE FROM active_mrz WHERE symbol = %s", (replay.symbol,))
            return
        cursor.execute(
            """
            INSERT INTO active_mrz (
                symbol, route_owner, core_mrz_lower, core_mrz_upper,
                core_mrz_midpoint, structural_location, confirming_observation_count,
                supporting_observation_count,
                activation_source,
                activated_at, activation_event_id,
                formation_started_at, formation_completed_at,
                formation_duration_seconds,
                ipda_20w_high_at_activation, ipda_20w_low_at_activation,
                ipda_width_at_activation, normalized_span_at_activation,
                instrument_tick, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                clock_timestamp()
            )
            ON CONFLICT (symbol) DO UPDATE SET
                route_owner = EXCLUDED.route_owner,
                core_mrz_lower = EXCLUDED.core_mrz_lower,
                core_mrz_upper = EXCLUDED.core_mrz_upper,
                core_mrz_midpoint = EXCLUDED.core_mrz_midpoint,
                structural_location = EXCLUDED.structural_location,
                confirming_observation_count = EXCLUDED.confirming_observation_count,
                supporting_observation_count = EXCLUDED.supporting_observation_count,
                activation_source = EXCLUDED.activation_source,
                activated_at = EXCLUDED.activated_at,
                activation_event_id = EXCLUDED.activation_event_id,
                formation_started_at = EXCLUDED.formation_started_at,
                formation_completed_at = EXCLUDED.formation_completed_at,
                formation_duration_seconds = EXCLUDED.formation_duration_seconds,
                ipda_20w_high_at_activation = EXCLUDED.ipda_20w_high_at_activation,
                ipda_20w_low_at_activation = EXCLUDED.ipda_20w_low_at_activation,
                ipda_width_at_activation = EXCLUDED.ipda_width_at_activation,
                normalized_span_at_activation = EXCLUDED.normalized_span_at_activation,
                instrument_tick = EXCLUDED.instrument_tick,
                updated_at = clock_timestamp()
            """,
            (
                active.symbol,
                active.route_owner.value,
                active.core_mrz_lower,
                active.core_mrz_upper,
                active.core_mrz_midpoint,
                active.structural_location.value,
                active.confirming_observation_count,
                active.supporting_observation_count,
                active.activation_source.value,
                active.activated_at,
                active.activation_event_id,
                active.formation_started_at,
                active.formation_completed_at,
                active.formation_duration_seconds,
                active.ipda_20w_high_at_activation,
                active.ipda_20w_low_at_activation,
                active.ipda_width_at_activation,
                active.normalized_span_at_activation,
                active.instrument_tick,
            ),
        )
        self._replace_production_confirmation(cursor, replay)

    def promote_current_near_miss(
        self,
        symbol: str,
        route: Route,
        candidate_identity: str,
    ) -> PromotionOutcome:
        normalized = normalize_symbol(symbol)
        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (normalized,),
                )
                cursor.execute(
                    "SELECT * FROM operator_mrz_promotions WHERE symbol = %s",
                    (normalized,),
                )
                existing_promotion = cursor.fetchone()
                cursor.execute("SELECT * FROM active_mrz WHERE symbol = %s", (normalized,))
                existing_active = active_from_row(cursor.fetchone())
                if existing_promotion is not None:
                    if (
                        str(existing_promotion["candidate_identity"])
                        == candidate_identity
                        and existing_active is not None
                    ):
                        return PromotionOutcome(
                            symbol=normalized,
                            route=Route(str(existing_promotion["route_owner"])),
                            candidate_identity=candidate_identity,
                            duplicate=True,
                            trigger_event_id=str(existing_promotion["trigger_event_id"]),
                        )
                    raise PromotionConflict(
                        "active_mrz_exists",
                        f"{normalized} already has authoritative MRZ history.",
                    )
                if existing_active is not None:
                    raise PromotionConflict(
                        "active_mrz_exists",
                        f"{normalized} already has an authoritative MRZ.",
                    )

                cursor.execute(
                    """
                    SELECT * FROM observations
                    WHERE schema_version = '4.3'
                    ORDER BY symbol ASC, route ASC,
                             observed_at ASC, received_at ASC, id ASC
                    """
                )
                observations = tuple(
                    observation_from_row(row) for row in cursor.fetchall()
                )
                cursor.execute("SELECT symbol FROM active_mrz ORDER BY symbol")
                active_symbols = {str(row["symbol"]) for row in cursor.fetchall()}
                candidates = current_production_near_misses(
                    observations,
                    active_symbols=active_symbols,
                )
                candidate = next(
                    (
                        row
                        for row in candidates
                        if row["symbol"] == normalized and row["route"] == route.value
                    ),
                    None,
                )
                if candidate is None:
                    raise PromotionConflict(
                        "candidate_no_longer_current",
                        "Candidate changed or is no longer a current production near miss. "
                        "Review the latest report before promoting.",
                    )
                if candidate["candidate_identity"] != candidate_identity:
                    raise PromotionConflict(
                        "candidate_changed",
                        "Candidate changed. Review the latest near miss before promoting.",
                    )

                supporting_ids = tuple(candidate["supporting_observation_ids"])
                observations_by_id = {item.event_id: item for item in observations}
                try:
                    supporting = tuple(
                        observations_by_id[event_id] for event_id in supporting_ids
                    )
                    trigger = observations_by_id[str(candidate["candidate_event_id"])]
                except KeyError as exc:
                    raise PromotionConflict(
                        "candidate_evidence_missing",
                        "Canonical candidate evidence is no longer available.",
                    ) from exc
                if (
                    len(supporting) < 4
                    or any(item.symbol != normalized or item.route is not route for item in supporting)
                    or trigger.event_id not in supporting_ids
                ):
                    raise PromotionConflict(
                        "candidate_evidence_invalid",
                        "Canonical candidate evidence is not promotion-eligible.",
                    )

                lower = Decimal(str(candidate["candidate_lower_boundary"]))
                upper = Decimal(str(candidate["candidate_upper_boundary"]))
                midpoint = Decimal(str(candidate["candidate_midpoint"]))
                required = Decimal(str(candidate["minimum_required_allowance_pct"]))
                threshold = Decimal(str(candidate["configured_allowance_pct"]))
                structural_location = classify_structural_location(
                    route,
                    midpoint,
                    trigger.ipda_20w_high,
                    trigger.ipda_20w_low,
                )
                if structural_location is None:
                    raise PromotionConflict(
                        "candidate_structurally_ineligible",
                        "Candidate no longer satisfies structural eligibility.",
                    )
                cluster = Cluster(
                    members=supporting,
                    lower=lower,
                    upper=upper,
                    midpoint=midpoint,
                    normalized_span=required / Decimal("100"),
                )
                cursor.execute("SELECT clock_timestamp() AS promoted_at")
                promoted_at = cursor.fetchone()["promoted_at"]
                promotion_key = f"OPERATOR_PROMOTION:{candidate_identity}"
                cursor.execute(
                    """
                    INSERT INTO operator_mrz_promotions (
                        promotion_key, symbol, route_owner, candidate_identity,
                        evaluator_identity, candidate_lower, candidate_upper,
                        candidate_midpoint, structural_location, normalized_span,
                        minimum_required_allowance_pct, production_threshold_pct,
                        shortfall_percentage_points, supporting_observation_count,
                        supporting_observation_ids, candidate_timestamp,
                        trigger_event_id, formation_started_at,
                        formation_completed_at, formation_duration_seconds,
                        ipda_20w_high, ipda_20w_low, ipda_width,
                        instrument_tick, promoted_at, operator_identity
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, NULL
                    )
                    RETURNING *
                    """,
                    (
                        promotion_key,
                        normalized,
                        route.value,
                        candidate_identity,
                        candidate["evaluator_identity"],
                        lower,
                        upper,
                        midpoint,
                        structural_location.value,
                        cluster.normalized_span,
                        required,
                        threshold,
                        required - threshold,
                        cluster.observation_count,
                        Json(list(supporting_ids)),
                        trigger.observed_at,
                        trigger.event_id,
                        cluster.formation_started_at,
                        cluster.formation_completed_at,
                        cluster.formation_duration_seconds,
                        trigger.ipda_20w_high,
                        trigger.ipda_20w_low,
                        trigger.ipda_width,
                        effective_instrument_tick(cluster),
                        promoted_at,
                    ),
                )
                promoted_activation = promoted_active_from_row(cursor.fetchone())
                if promoted_activation is None:
                    raise RuntimeError("persisted promotion did not produce authority")
                symbol_observations = tuple(
                    item for item in observations if item.symbol == normalized
                )
                replay = replay_symbol(
                    symbol_observations,
                    promoted_activation=promoted_activation,
                )
                if replay.active_mrz is None:
                    raise RuntimeError("operator promotion replay produced no authority")
                self._replace_derived_state(cursor, replay)
                cursor.execute(
                    """
                    UPDATE current_production_near_miss_episodes
                    SET ended_at = %s, ended_reason = 'OPERATOR_PROMOTED'
                    WHERE symbol = %s AND ended_at IS NULL
                    """,
                    (promoted_at, normalized),
                )
                return PromotionOutcome(
                    symbol=normalized,
                    route=route,
                    candidate_identity=candidate_identity,
                    duplicate=False,
                    trigger_event_id=trigger.event_id,
                )

    def _replace_production_confirmation(
        self,
        cursor: RealDictCursor,
        replay: ReplayResult,
    ) -> None:
        cursor.execute(
            "SELECT * FROM operator_mrz_promotions WHERE symbol = %s",
            (replay.symbol,),
        )
        promotion = cursor.fetchone()
        if promotion is None:
            return
        cursor.execute(
            "DELETE FROM mrz_production_confirmations WHERE promotion_id = %s",
            (promotion["id"],),
        )
        promoted_active = promoted_active_from_row(promotion)
        if promoted_active is None:
            return
        cursor.execute(
            """
            SELECT * FROM observations
            WHERE symbol = %s
            ORDER BY observed_at ASC, received_at ASC, id ASC
            """,
            (replay.symbol,),
        )
        observations = tuple(
            observation_from_row(row) for row in cursor.fetchall()
        )
        migration_triggers = {
            transition.trigger_event_id
            for transition in replay.transitions
            if transition.event_type.value == "MRZ_MIGRATED"
        }
        windows: dict[Route, deque[Observation]] = {
            Route.BTD: deque(maxlen=ROUTE_OBSERVATION_WINDOW),
            Route.STR: deque(maxlen=ROUTE_OBSERVATION_WINDOW),
        }
        promotion_seen = False
        for incoming in observations:
            windows[incoming.route].append(incoming)
            if not promotion_seen:
                promotion_seen = incoming.event_id == promoted_active.activation_event_id
                continue
            if incoming.event_id in migration_triggers:
                break
            evaluation = evaluate_concentration(
                tuple(windows[incoming.route]),
                incoming.route,
            )
            if (
                evaluation.result is not ConcentrationResult.QUALIFIES
                or evaluation.cluster is None
            ):
                continue
            cluster = evaluation.cluster
            location = classify_structural_location(
                incoming.route,
                cluster.midpoint,
                incoming.ipda_20w_high,
                incoming.ipda_20w_low,
            )
            if location is None:
                continue
            supporting_ids = [item.event_id for item in cluster.members]
            identity_payload = {
                "symbol": replay.symbol,
                "route": incoming.route.value,
                "evaluator_identity": "A-4-1:production-concentration-v1",
                "candidate_lower": str(cluster.lower),
                "candidate_upper": str(cluster.upper),
                "candidate_midpoint": str(cluster.midpoint),
                "supporting_observation_ids": supporting_ids,
                "trigger_event_id": incoming.event_id,
                "qualified_at": iso(incoming.observed_at),
            }
            evaluation_identity = hashlib.sha256(
                json.dumps(
                    identity_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            confirmation_key = (
                f"{promotion['promotion_key']}:PRODUCTION_CONFIRMATION:"
                f"{evaluation_identity}"
            )
            required = cluster.normalized_span * Decimal("100")
            cursor.execute(
                """
                INSERT INTO mrz_production_confirmations (
                    confirmation_key, promotion_id, symbol, route_owner,
                    evaluator_identity, evaluation_identity,
                    qualified_lower, qualified_upper, qualified_midpoint,
                    structural_location, qualified_at, trigger_event_id,
                    normalized_span, minimum_required_allowance_pct,
                    production_threshold_pct, supporting_observation_count,
                    supporting_observation_ids
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    confirmation_key,
                    promotion["id"],
                    replay.symbol,
                    incoming.route.value,
                    "A-4-1:production-concentration-v1",
                    evaluation_identity,
                    cluster.lower,
                    cluster.upper,
                    cluster.midpoint,
                    location.value,
                    incoming.observed_at,
                    incoming.event_id,
                    cluster.normalized_span,
                    required,
                    Decimal("1.00"),
                    cluster.observation_count,
                    Json(supporting_ids),
                ),
            )
            break

    def _sync_near_miss_episodes(
        self,
        cursor: RealDictCursor,
        *,
        symbol: str,
        trigger_event_id: str,
        was_active: bool,
    ) -> None:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("CURRENT_PRODUCTION_NEAR_MISS_EPISODES",),
        )
        cursor.execute(
            """
            SELECT * FROM observations
            WHERE schema_version = '4.3'
            ORDER BY symbol ASC, route ASC,
                     observed_at ASC, received_at ASC, id ASC
            """
        )
        observations = tuple(
            observation_from_row(row) for row in cursor.fetchall()
        )
        previous_observations = tuple(
            item for item in observations if item.event_id != trigger_event_id
        )
        cursor.execute("SELECT symbol FROM active_mrz ORDER BY symbol")
        current_active = {str(row["symbol"]) for row in cursor.fetchall()}
        previous_active = set(current_active)
        if not was_active:
            previous_active.discard(symbol)
        current_candidates = current_production_near_misses(
            observations,
            active_symbols=current_active,
        )
        previous_candidates = current_production_near_misses(
            previous_observations,
            active_symbols=previous_active,
        )
        current_by_history = {
            (str(row["symbol"]), str(row["route"])): row
            for row in current_candidates
        }
        previous_by_history = {
            (str(row["symbol"]), str(row["route"])): row
            for row in previous_candidates
        }
        cursor.execute(
            """
            SELECT * FROM current_production_near_miss_episodes
            WHERE ended_at IS NULL
            FOR UPDATE
            """
        )
        open_by_history = {
            (str(row["symbol"]), str(row["route_owner"])): row
            for row in cursor.fetchall()
        }
        for history, episode in open_by_history.items():
            if history in current_by_history:
                continue
            reason = (
                "SYMBOL_ACTIVATED"
                if history[0] in current_active
                else "NO_LONGER_CURRENT"
            )
            cursor.execute(
                """
                UPDATE current_production_near_miss_episodes
                SET ended_at = clock_timestamp(), ended_reason = %s
                WHERE id = %s AND ended_at IS NULL
                """,
                (reason, episode["id"]),
            )
        for history, candidate in current_by_history.items():
            if history in open_by_history:
                continue
            candidate_symbol, route_value = history
            previous = previous_by_history.get(history)
            source = previous or candidate
            deliverable = previous is None
            source_event_id = (
                trigger_event_id
                if deliverable
                else str(source["candidate_event_id"])
            )
            episode_key = (
                f"MRZ_NEAR_MISS:{candidate_symbol}:{route_value}:"
                f"{source_event_id}:{source['candidate_identity']}"
            )
            cursor.execute(
                """
                INSERT INTO current_production_near_miss_episodes (
                    episode_key, symbol, route_owner,
                    source_trigger_event_id, candidate_identity,
                    evaluator_identity, candidate_lower, candidate_upper,
                    candidate_midpoint, structural_location,
                    minimum_required_allowance_pct,
                    production_threshold_pct, shortfall_percentage_points,
                    supporting_observation_count, supporting_observation_ids,
                    candidate_timestamp, deliverable
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (episode_key) DO NOTHING
                """,
                (
                    episode_key,
                    candidate_symbol,
                    route_value,
                    source_event_id,
                    source["candidate_identity"],
                    source["evaluator_identity"],
                    Decimal(str(source["candidate_lower_boundary"])),
                    Decimal(str(source["candidate_upper_boundary"])),
                    Decimal(str(source["candidate_midpoint"])),
                    source["structural_location"],
                    Decimal(str(source["minimum_required_allowance_pct"])),
                    Decimal(str(source["configured_allowance_pct"])),
                    Decimal(str(source["shortfall_percentage_points"])),
                    int(source["candidate_observation_count"]),
                    Json(list(source["supporting_observation_ids"])),
                    source["candidate_timestamp"],
                    deliverable,
                ),
            )

    def record_rejection(
        self,
        *,
        raw_body: bytes,
        event_id: str | None,
        reason_code: str,
        diagnostics: Mapping[str, Any],
        sanitized_payload: Any,
    ) -> None:
        fingerprint = hashlib.sha256(raw_body).hexdigest()
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ingestion_rejections (
                        event_id, reason_code, diagnostics, payload_fingerprint, sanitized_payload
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        event_id,
                        reason_code,
                        Json(dict(diagnostics)),
                        fingerprint,
                        Json(sanitized_payload) if sanitized_payload is not None else None,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE ingestion_metrics
                    SET rejected_payload_count = rejected_payload_count + 1
                    WHERE singleton = TRUE
                    """
                )

    def symbol_detail(self, symbol: str) -> dict[str, Any] | None:
        normalized = normalize_symbol(symbol)
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM (
                        (
                            SELECT *
                            FROM observations
                            WHERE symbol = %s AND route = 'BTD'
                            ORDER BY observed_at DESC, received_at DESC, id DESC
                            LIMIT %s
                        )
                        UNION ALL
                        (
                            SELECT *
                            FROM observations
                            WHERE symbol = %s AND route = 'STR'
                            ORDER BY observed_at DESC, received_at DESC, id DESC
                            LIMIT %s
                        )
                    ) AS retained_route_windows
                    ORDER BY observed_at ASC, received_at ASC, id ASC
                    """,
                    (
                        normalized,
                        ROUTE_OBSERVATION_WINDOW,
                        normalized,
                        ROUTE_OBSERVATION_WINDOW,
                    ),
                )
                window_rows = cursor.fetchall()
                if not window_rows:
                    return None
                route_windows = {
                    route: tuple(
                        observation_from_row(row)
                        for row in window_rows
                        if row["route"] == route.value
                    )
                    for route in Route
                }
                latest = max(
                    window_rows,
                    key=lambda row: (row["observed_at"], row["received_at"], row["id"]),
                )
                window_counts = {
                    "btd_window_observation_count": len(route_windows[Route.BTD]),
                    "btd_window_started_at": (
                        route_windows[Route.BTD][0].observed_at
                        if route_windows[Route.BTD]
                        else None
                    ),
                    "str_window_observation_count": len(route_windows[Route.STR]),
                    "str_window_started_at": (
                        route_windows[Route.STR][0].observed_at
                        if route_windows[Route.STR]
                        else None
                    ),
                }
                cursor.execute("SELECT * FROM active_mrz WHERE symbol = %s", (normalized,))
                active = active_from_row(cursor.fetchone())
                migration = current_migration_provenance(cursor, active)
                cursor.execute(
                    "SELECT * FROM operator_mrz_promotions WHERE symbol = %s",
                    (normalized,),
                )
                promotion = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT c.*
                    FROM mrz_production_confirmations c
                    INNER JOIN operator_mrz_promotions p ON p.id = c.promotion_id
                    WHERE p.symbol = %s
                    ORDER BY c.qualified_at DESC, c.id DESC
                    LIMIT 1
                    """,
                    (normalized,),
                )
                production_confirmation = cursor.fetchone()
                concentration_checks = None
                if active is None:
                    concentration_checks = {
                        route: evaluate_concentration(route_windows[route], route).diagnostic
                        for route in Route
                    }
                    for diagnostic in concentration_checks.values():
                        if diagnostic.result is ConcentrationResult.QUALIFIES:
                            log_unestablished_qualifying_concentration(normalized, diagnostic)
                return detail_payload(
                    normalized,
                    latest,
                    active,
                    window_counts,
                    concentration_checks,
                    migration,
                    promotion_provenance_payload(promotion),
                    production_confirmation_payload(production_confirmation),
                )
        finally:
            connection.close()

    def schema_43_observations(self) -> tuple[Observation, ...]:
        """Return the complete canonical sample for read-only diagnostics."""
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low, observed_at, received_at
                    FROM observations
                    WHERE schema_version = '4.3'
                    ORDER BY symbol ASC, route ASC,
                             observed_at ASC, received_at ASC, id ASC
                    """
                )
                return tuple(observation_from_row(row) for row in cursor.fetchall())
        finally:
            connection.close()

    def activation_feasibility_inputs(
        self,
    ) -> tuple[tuple[Observation, ...], tuple[str, ...]]:
        """Return one current snapshot for feasibility and promotion visibility."""
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low, observed_at, received_at
                    FROM observations
                    WHERE schema_version = '4.3'
                    ORDER BY symbol ASC, route ASC,
                             observed_at ASC, received_at ASC, id ASC
                    """
                )
                observations = tuple(
                    observation_from_row(row) for row in cursor.fetchall()
                )
                cursor.execute("SELECT symbol FROM active_mrz ORDER BY symbol")
                active_symbols = tuple(str(row["symbol"]) for row in cursor.fetchall())
                return observations, active_symbols
        finally:
            connection.close()

    def mrz_robustness_inputs(
        self,
    ) -> tuple[
        tuple[ActiveMRZ, ...],
        tuple[Observation, ...],
        dict[str, dict[str, Any]],
    ]:
        """Return one consistent read-only snapshot for post-activation diagnostics."""
        connection = connect(self.database_url)
        try:
            connection.set_session(
                readonly=True,
                isolation_level="REPEATABLE READ",
            )
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM active_mrz ORDER BY symbol ASC")
                active_mrzs = tuple(
                    active
                    for active in (
                        active_from_row(row) for row in cursor.fetchall()
                    )
                    if active is not None
                )
                if not active_mrzs:
                    return (), (), {}
                cursor.execute(
                    """
                    SELECT
                        e.symbol, e.occurred_at, e.trigger_event_id, e.route_owner,
                        e.old_core_mrz_lower, e.old_core_mrz_upper,
                        e.new_core_mrz_lower, e.new_core_mrz_upper,
                        e.new_core_mrz_midpoint,
                        previous_authority.occurred_at AS previous_activated_at
                    FROM mrz_events e
                    INNER JOIN active_mrz a
                        ON a.symbol = e.symbol
                       AND a.activation_event_id = e.trigger_event_id
                       AND a.activated_at = e.occurred_at
                       AND a.route_owner = e.route_owner
                       AND a.core_mrz_lower = e.new_core_mrz_lower
                       AND a.core_mrz_upper = e.new_core_mrz_upper
                       AND a.core_mrz_midpoint = e.new_core_mrz_midpoint
                    LEFT JOIN LATERAL (
                        SELECT source_event.occurred_at
                        FROM mrz_events source_event
                        WHERE source_event.symbol = e.symbol
                          AND source_event.sequence < e.sequence
                          AND source_event.event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')
                          AND source_event.route_owner = e.previous_route_owner
                          AND source_event.new_core_mrz_lower = e.old_core_mrz_lower
                          AND source_event.new_core_mrz_upper = e.old_core_mrz_upper
                          AND source_event.occurred_at <= e.occurred_at
                        ORDER BY source_event.sequence DESC
                        LIMIT 1
                    ) previous_authority ON TRUE
                    WHERE e.event_type = 'MRZ_MIGRATED'
                      AND e.symbol = ANY(%s)
                    ORDER BY e.symbol ASC, e.sequence DESC
                    """,
                    ([active.symbol for active in active_mrzs],),
                )
                migration_by_symbol = {
                    str(row["symbol"]): migration_provenance_payload(row)
                    for row in cursor.fetchall()
                }
                cursor.execute(
                    """
                    SELECT
                        id, event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low, observed_at, received_at
                    FROM observations
                    WHERE schema_version = '4.3'
                      AND symbol = ANY(%s)
                    ORDER BY symbol ASC, observed_at ASC, received_at ASC, id ASC
                    """,
                    ([active.symbol for active in active_mrzs],),
                )
                observations = tuple(
                    observation_from_row(row) for row in cursor.fetchall()
                )
                migration_provenance = {
                    active.symbol: migration_by_symbol.get(
                        active.symbol,
                        migration_provenance_payload(None),
                    )
                    for active in active_mrzs
                }
                return active_mrzs, observations, migration_provenance
        finally:
            connection.close()

    def location_migration_tendency(self) -> dict[str, dict[str, int | float | None]]:
        """Aggregate canonical MRZ transitions by the old authority's location."""
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    WITH authoritative_migrations AS (
                        SELECT DISTINCT ON (current_event.event_key)
                            current_event.event_key,
                            current_event.occurred_at,
                            current_event.sequence,
                            previous_authority.structural_location
                                AS starting_structural_location,
                            CASE
                                WHEN current_event.new_core_mrz_midpoint >
                                     (
                                         current_event.old_core_mrz_lower
                                         + current_event.old_core_mrz_upper
                                     ) / 2
                                    THEN 'HIGHER'
                                WHEN current_event.new_core_mrz_midpoint <
                                     (
                                         current_event.old_core_mrz_lower
                                         + current_event.old_core_mrz_upper
                                     ) / 2
                                    THEN 'LOWER'
                                ELSE 'EQUAL'
                            END AS direction
                        FROM mrz_events current_event
                        INNER JOIN LATERAL (
                            SELECT source_event.structural_location
                            FROM mrz_events source_event
                            WHERE source_event.symbol = current_event.symbol
                              AND source_event.sequence < current_event.sequence
                              AND source_event.event_type IN (
                                  'MRZ_ACTIVATED', 'MRZ_MIGRATED'
                              )
                              AND source_event.route_owner =
                                  current_event.previous_route_owner
                              AND source_event.new_core_mrz_lower =
                                  current_event.old_core_mrz_lower
                              AND source_event.new_core_mrz_upper =
                                  current_event.old_core_mrz_upper
                              AND source_event.occurred_at <= current_event.occurred_at
                            ORDER BY
                                source_event.occurred_at DESC,
                                source_event.sequence DESC
                            LIMIT 1
                        ) previous_authority ON TRUE
                        WHERE current_event.event_type = 'MRZ_MIGRATED'
                        ORDER BY
                            current_event.event_key,
                            current_event.occurred_at ASC,
                            current_event.sequence ASC
                    )
                    SELECT
                        starting_structural_location,
                        COUNT(*) FILTER (WHERE direction = 'HIGHER') AS higher_count,
                        COUNT(*) FILTER (WHERE direction = 'LOWER') AS lower_count,
                        COUNT(*) FILTER (WHERE direction = 'EQUAL') AS equal_count
                    FROM authoritative_migrations
                    GROUP BY starting_structural_location
                    ORDER BY starting_structural_location ASC
                    """
                )
                return location_migration_tendency_payload(cursor.fetchall())
        finally:
            connection.close()

    def saved_groups(self) -> list[dict[str, Any]]:
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True)
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, member_symbols, created_at, updated_at
                    FROM saved_symbol_groups
                    ORDER BY lower(name) ASC, id ASC
                    """
                )
                return [saved_group_payload(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def create_saved_group(
        self,
        name: str,
        members: Sequence[str],
    ) -> dict[str, Any]:
        canonical_members = normalize_saved_group_members(members)
        try:
            with transaction(self.database_url) as connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        INSERT INTO saved_symbol_groups (name, member_symbols)
                        VALUES (%s, %s)
                        RETURNING id, name, member_symbols, created_at, updated_at
                        """,
                        (name, canonical_members),
                    )
                    return saved_group_payload(cursor.fetchone())
        except errors.UniqueViolation as exc:
            raise SavedGroupNameConflict("group name already exists") from exc

    def update_saved_group(
        self,
        group_id: int,
        name: str,
        members: Sequence[str],
    ) -> dict[str, Any] | None:
        canonical_members = normalize_saved_group_members(members)
        try:
            with transaction(self.database_url) as connection:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        """
                        UPDATE saved_symbol_groups
                        SET name = %s,
                            member_symbols = %s,
                            updated_at = clock_timestamp()
                        WHERE id = %s
                        RETURNING id, name, member_symbols, created_at, updated_at
                        """,
                        (name, canonical_members, group_id),
                    )
                    row = cursor.fetchone()
                    return saved_group_payload(row) if row else None
        except errors.UniqueViolation as exc:
            raise SavedGroupNameConflict("group name already exists") from exc

    def delete_saved_group(self, group_id: int) -> dict[str, Any] | None:
        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    DELETE FROM saved_symbol_groups
                    WHERE id = %s
                    RETURNING id, name, member_symbols, created_at, updated_at
                    """,
                    (group_id,),
                )
                row = cursor.fetchone()
                return saved_group_payload(row) if row else None

    def saved_group_report(self, group_id: int) -> dict[str, Any] | None:
        """Return a current cohort snapshot without creating group-owned analytics."""
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, member_symbols, created_at, updated_at
                    FROM saved_symbol_groups
                    WHERE id = %s
                    """,
                    (group_id,),
                )
                group_row = cursor.fetchone()
                if group_row is None:
                    return None
                group = saved_group_payload(group_row)
                cursor.execute(
                    """
                    WITH members(symbol, member_order) AS (
                        SELECT selected.symbol, selected.member_order
                        FROM unnest(%s::text[]) WITH ORDINALITY
                            AS selected(symbol, member_order)
                    )
                    SELECT
                        members.symbol,
                        members.member_order,
                        latest.observation_price,
                        latest.ipda_20w_high,
                        latest.ipda_20w_low,
                        (active.symbol IS NOT NULL) AS has_active_mrz,
                        active.route_owner,
                        migration.old_core_mrz_lower,
                        migration.old_core_mrz_upper,
                        migration.new_core_mrz_midpoint
                    FROM members
                    LEFT JOIN LATERAL (
                        SELECT observation_price, ipda_20w_high, ipda_20w_low
                        FROM observations
                        WHERE symbol = members.symbol
                        ORDER BY observed_at DESC, received_at DESC, id DESC
                        LIMIT 1
                    ) latest ON TRUE
                    LEFT JOIN active_mrz active ON active.symbol = members.symbol
                    LEFT JOIN LATERAL (
                        SELECT
                            old_core_mrz_lower,
                            old_core_mrz_upper,
                            new_core_mrz_midpoint
                        FROM mrz_events
                        WHERE symbol = members.symbol
                          AND event_type = 'MRZ_MIGRATED'
                        ORDER BY sequence DESC
                        LIMIT 1
                    ) migration ON TRUE
                    ORDER BY members.member_order ASC
                    """,
                    (group["members"],),
                )

                locations = {key: 0 for key in GROUP_LOCATION_KEYS}
                active_count = 0
                routes = {"BTD": 0, "STR": 0, "unestablished": 0}
                breadth = {"higher": 0, "lower": 0, "no_migration": 0}
                for row in cursor.fetchall():
                    if row["observation_price"] is not None:
                        location = current_price_location_value(row)
                        if location in locations:
                            locations[location] += 1
                    if row["has_active_mrz"]:
                        active_count += 1
                        route = str(row["route_owner"])
                        if route in ("BTD", "STR"):
                            routes[route] += 1
                    else:
                        routes["unestablished"] += 1
                    direction = migration_direction(row)
                    breadth[direction or "no_migration"] += 1

                return {
                    **group,
                    "current_state": {
                        "location": locations,
                        "active_mrz": {
                            "count": active_count,
                            "total": len(group["members"]),
                        },
                        "migration_breadth": breadth,
                        "route": routes,
                    },
                }
        finally:
            connection.close()

    def saved_group_migration_path(self, group_id: int) -> dict[str, Any] | None:
        """Read the current canonical authority chain using domain chronology."""
        connection = connect(self.database_url)
        try:
            connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT id, name, member_symbols, created_at, updated_at
                    FROM saved_symbol_groups
                    WHERE id = %s
                    """,
                    (group_id,),
                )
                group_row = cursor.fetchone()
                if group_row is None:
                    return None
                group = saved_group_payload(group_row)
                cursor.execute(
                    """
                    WITH members(symbol, member_order) AS (
                        SELECT selected.symbol, selected.member_order
                        FROM unnest(%s::text[]) WITH ORDINALITY
                            AS selected(symbol, member_order)
                    )
                    SELECT
                        members.symbol,
                        members.member_order,
                        events.event_key,
                        events.sequence,
                        events.event_type,
                        events.route_owner,
                        events.occurred_at,
                        events.old_core_mrz_lower,
                        events.old_core_mrz_upper,
                        events.new_core_mrz_lower,
                        events.new_core_mrz_upper,
                        events.new_core_mrz_midpoint,
                        events.structural_location
                    FROM members
                    LEFT JOIN mrz_events events
                        ON events.symbol = members.symbol
                       AND events.event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')
                    ORDER BY
                        members.member_order ASC,
                        events.occurred_at ASC,
                        events.sequence ASC
                    """,
                    (group["members"],),
                )
                states_by_symbol = {symbol: [] for symbol in group["members"]}
                timestamps: list[datetime] = []
                for row in cursor.fetchall():
                    if row["event_key"] is None:
                        continue
                    location = str(row["structural_location"])
                    code, label = STRUCTURAL_LOCATION_PRESENTATION.get(
                        location,
                        ("—", "Unavailable"),
                    )
                    occurred_at = row["occurred_at"]
                    timestamps.append(occurred_at)
                    states_by_symbol[str(row["symbol"])].append(
                        {
                            "event_key": str(row["event_key"]),
                            "event_type": str(row["event_type"]),
                            "occurred_at": iso(occurred_at),
                            "route_owner": str(row["route_owner"]),
                            "location": location,
                            "location_code": code,
                            "location_label": label,
                            "lower": number(row["new_core_mrz_lower"]),
                            "upper": number(row["new_core_mrz_upper"]),
                            "midpoint": number(row["new_core_mrz_midpoint"]),
                            "direction": migration_direction(row),
                        }
                    )
                return {
                    **group,
                    "timeline": {
                        "started_at": iso(min(timestamps)) if timestamps else None,
                        "ended_at": iso(max(timestamps)) if timestamps else None,
                    },
                    "paths": [
                        {"symbol": symbol, "states": states_by_symbol[symbol]}
                        for symbol in group["members"]
                    ],
                }
        finally:
            connection.close()

    def symbols(self) -> list[dict[str, Any]]:
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    WITH latest_observations AS (
                        SELECT DISTINCT ON (o.symbol)
                            o.symbol, o.observation_price,
                            o.ipda_20w_high, o.ipda_20w_low, o.observed_at
                        FROM observations o
                        ORDER BY
                            o.symbol ASC,
                            o.observed_at DESC,
                            o.received_at DESC,
                            o.id DESC
                    )
                    SELECT
                        o.symbol,
                        o.observation_price AS latest_observation_price,
                        o.ipda_20w_high AS latest_ipda_20w_high,
                        o.ipda_20w_low AS latest_ipda_20w_low,
                        o.observed_at AS latest_observed_at,
                        a.route_owner, a.core_mrz_lower, a.core_mrz_upper,
                        a.core_mrz_midpoint, a.structural_location,
                        a.confirming_observation_count, a.activation_source,
                        EXISTS (
                            SELECT 1
                            FROM mrz_events e
                            WHERE e.symbol = a.symbol
                              AND e.event_type = 'MRZ_MIGRATED'
                              AND e.trigger_event_id = a.activation_event_id
                              AND e.occurred_at = a.activated_at
                              AND e.route_owner = a.route_owner
                              AND e.new_core_mrz_lower = a.core_mrz_lower
                              AND e.new_core_mrz_upper = a.core_mrz_upper
                              AND e.new_core_mrz_midpoint = a.core_mrz_midpoint
                        ) AS has_migrated,
                        w.id, w.event_id, w.schema_version,
                        w.route, w.observation_type,
                        w.observation_price, w.observation_price_tick,
                        w.ipda_20w_high, w.ipda_20w_low,
                        w.observed_at, w.received_at
                    FROM latest_observations o
                    LEFT JOIN active_mrz a ON a.symbol = o.symbol
                    LEFT JOIN LATERAL (
                        (
                            SELECT
                                id, event_id, schema_version, route, observation_type,
                                observation_price, observation_price_tick,
                                ipda_20w_high, ipda_20w_low, observed_at, received_at
                            FROM observations
                            WHERE symbol = o.symbol AND route = 'BTD'
                            ORDER BY observed_at DESC, received_at DESC, id DESC
                            LIMIT %s
                        )
                        UNION ALL
                        (
                            SELECT
                                id, event_id, schema_version, route, observation_type,
                                observation_price, observation_price_tick,
                                ipda_20w_high, ipda_20w_low, observed_at, received_at
                            FROM observations
                            WHERE symbol = o.symbol AND route = 'STR'
                            ORDER BY observed_at DESC, received_at DESC, id DESC
                            LIMIT %s
                        )
                    ) w ON TRUE
                    ORDER BY o.symbol ASC, w.observed_at ASC, w.received_at ASC, w.id ASC
                    """,
                    (ROUTE_OBSERVATION_WINDOW, ROUTE_OBSERVATION_WINDOW),
                )
                rows_by_symbol: dict[str, list[Mapping[str, Any]]] = {}
                for row in cursor.fetchall():
                    rows_by_symbol.setdefault(str(row["symbol"]), []).append(row)

                payloads = []
                for symbol, rows in rows_by_symbol.items():
                    anchor = rows[0]
                    route_windows = {
                        route: tuple(
                            observation_from_row(row)
                            for row in rows
                            if row["route"] == route.value
                        )
                        for route in Route
                    }
                    latest = {
                        "observation_price": anchor["latest_observation_price"],
                        "ipda_20w_high": anchor["latest_ipda_20w_high"],
                        "ipda_20w_low": anchor["latest_ipda_20w_low"],
                    }
                    payloads.append(
                        {
                            "symbol": symbol,
                            "mrz_status": (
                                "active" if anchor["route_owner"] else "unestablished"
                            ),
                            "route_owner": anchor["route_owner"],
                            "core_mrz_lower": number(anchor["core_mrz_lower"]),
                            "core_mrz_upper": number(anchor["core_mrz_upper"]),
                            "core_mrz_midpoint": number(anchor["core_mrz_midpoint"]),
                            "structural_location": anchor["structural_location"],
                            "activation_source": anchor["activation_source"],
                            "has_migrated": bool(anchor["has_migrated"]),
                            "confirming_observation_count": anchor[
                                "confirming_observation_count"
                            ],
                            "latest_observation_price": number(
                                anchor["latest_observation_price"]
                            ),
                            "latest_observed_at": iso(anchor["latest_observed_at"]),
                            "current_price_location": current_price_location_value(latest),
                            "btd_window_observation_count": len(route_windows[Route.BTD]),
                            "str_window_observation_count": len(route_windows[Route.STR]),
                            "concentration_ranking": concentration_ranking_payload(
                                route_windows
                            ),
                        }
                    )
                return payloads
        finally:
            connection.close()

    def health(self) -> dict[str, Any]:
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT 1 AS ok")
                cursor.fetchone()
                cursor.execute("SELECT * FROM ingestion_metrics WHERE singleton = TRUE")
                metrics = cursor.fetchone()
                cursor.execute("SELECT COUNT(DISTINCT symbol) AS count FROM observations")
                symbols = cursor.fetchone()["count"]
                cursor.execute("SELECT COUNT(*) AS count FROM active_mrz")
                active = cursor.fetchone()["count"]
                return {
                    "status": "ok",
                    "application": "ok",
                    "database": "ok",
                    "schema_version": "4.3",
                    "latest_accepted_webhook_at": iso(metrics["latest_accepted_webhook_at"]),
                    "accepted_payload_count": int(metrics["accepted_payload_count"]),
                    "rejected_payload_count": int(metrics["rejected_payload_count"]),
                    "duplicate_payload_count": int(metrics["duplicate_payload_count"]),
                    "active_symbol_count": int(symbols),
                    "active_mrz_count": int(active),
                }
        finally:
            connection.close()

    def audit_events(self, symbol: str) -> list[dict[str, Any]]:
        normalized = normalize_symbol(symbol)
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM mrz_events WHERE symbol = %s ORDER BY sequence ASC",
                    (normalized,),
                )
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()


def number(value: Any) -> float | None:
    return None if value is None else float(value)


def saved_group_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    members = [str(symbol) for symbol in row["member_symbols"]]
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "members": members,
        "member_count": len(members),
        "created_at": iso(row["created_at"]),
        "updated_at": iso(row["updated_at"]),
    }


def normalize_saved_group_members(members: Sequence[str]) -> list[str]:
    canonical_members = list(dict.fromkeys(normalize_symbol(symbol) for symbol in members))
    if not canonical_members:
        raise ValueError("at least one member is required")
    if len(canonical_members) > 100:
        raise ValueError("a saved group cannot contain more than 100 members")
    return canonical_members


def migration_direction(row: Mapping[str, Any]) -> str | None:
    if (
        row.get("old_core_mrz_lower") is None
        or row.get("old_core_mrz_upper") is None
        or row.get("new_core_mrz_midpoint") is None
    ):
        return None
    old_midpoint = (
        Decimal(row["old_core_mrz_lower"])
        + Decimal(row["old_core_mrz_upper"])
    ) / Decimal("2")
    new_midpoint = Decimal(row["new_core_mrz_midpoint"])
    if new_midpoint > old_midpoint:
        return "higher"
    if new_midpoint < old_midpoint:
        return "lower"
    return None


def iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat().replace("+00:00", "Z")


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def concentration_diagnostic_payload(
    diagnostic: ConcentrationDiagnostic,
) -> dict[str, Any]:
    return {
        "route": diagnostic.route.value,
        "retained_observation_count": diagnostic.retained_observation_count,
        "minimum_required_count": diagnostic.minimum_required_count,
        "newest_observation_included": diagnostic.newest_observation_included,
        "tested_window_count": diagnostic.tested_window_count,
        "selected_observation_count": diagnostic.selected_observation_count,
        "selected_lower": decimal_text(diagnostic.selected_lower),
        "selected_upper": decimal_text(diagnostic.selected_upper),
        "observed_span": decimal_text(diagnostic.observed_span),
        "ipda_20w_high": decimal_text(diagnostic.ipda_20w_high),
        "ipda_20w_low": decimal_text(diagnostic.ipda_20w_low),
        "ipda_width": decimal_text(diagnostic.ipda_width),
        "concentration_threshold": decimal_text(diagnostic.concentration_threshold),
        "allowance": decimal_text(diagnostic.allowance),
        "normalized_span": decimal_text(diagnostic.normalized_span),
        "minimum_required_allowance_pct": decimal_text(
            diagnostic.minimum_required_allowance_pct
        ),
        "configured_allowance_pct": decimal_text(diagnostic.configured_allowance_pct),
        "allowance_difference_pct_points": decimal_text(
            diagnostic.allowance_difference_pct_points
        ),
        "allowance_comparison": diagnostic.allowance_comparison,
        "proposed_midpoint": decimal_text(diagnostic.proposed_midpoint),
        "proposed_structural_location": (
            diagnostic.proposed_structural_location.value
            if diagnostic.proposed_structural_location
            else None
        ),
        "concentration_passed": diagnostic.concentration_passed,
        "structural_eligibility_passed": diagnostic.structural_eligibility_passed,
        "result": diagnostic.result.value,
    }


def log_unestablished_qualifying_concentration(
    symbol: str,
    diagnostic: ConcentrationDiagnostic,
) -> None:
    LOGGER.error(
        "Concentration qualifies without active MRZ",
        extra={
            "symbol": symbol,
            "route_owner": diagnostic.route.value,
            "concentration_result": diagnostic.result.value,
            "retained_observation_count": diagnostic.retained_observation_count,
            "newest_observation_id": diagnostic.newest_observation_id,
            "selected_observation_ids": list(diagnostic.selected_observation_ids),
            "observed_span": decimal_text(diagnostic.observed_span),
            "allowance": decimal_text(diagnostic.allowance),
        },
    )


def promotion_provenance_payload(
    row: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "promotion_key": str(row["promotion_key"]),
        "candidate_identity": str(row["candidate_identity"]),
        "evaluator_identity": str(row["evaluator_identity"]),
        "route": str(row["route_owner"]),
        "candidate_lower": number(row["candidate_lower"]),
        "candidate_upper": number(row["candidate_upper"]),
        "candidate_midpoint": number(row["candidate_midpoint"]),
        "structural_location": str(row["structural_location"]),
        "promoted_at": iso(row["promoted_at"]),
        "minimum_required_allowance_pct": number(
            row["minimum_required_allowance_pct"]
        ),
        "production_threshold_pct": number(row["production_threshold_pct"]),
        "shortfall_percentage_points": number(row["shortfall_percentage_points"]),
        "supporting_observation_count": int(row["supporting_observation_count"]),
        "supporting_observation_ids": list(row["supporting_observation_ids"]),
        "candidate_timestamp": iso(row["candidate_timestamp"]),
        "operator_identity": row.get("operator_identity"),
    }


def production_confirmation_payload(
    row: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "confirmation_key": str(row["confirmation_key"]),
        "evaluation_identity": str(row["evaluation_identity"]),
        "evaluator_identity": str(row["evaluator_identity"]),
        "route": str(row["route_owner"]),
        "qualified_lower": number(row["qualified_lower"]),
        "qualified_upper": number(row["qualified_upper"]),
        "qualified_midpoint": number(row["qualified_midpoint"]),
        "structural_location": str(row["structural_location"]),
        "qualified_at": iso(row["qualified_at"]),
        "normalized_span": number(row["normalized_span"]),
        "minimum_required_allowance_pct": number(
            row["minimum_required_allowance_pct"]
        ),
        "production_threshold_pct": number(row["production_threshold_pct"]),
        "supporting_observation_count": int(row["supporting_observation_count"]),
        "supporting_observation_ids": list(row["supporting_observation_ids"]),
        "trigger_event_id": str(row["trigger_event_id"]),
    }


def detail_payload(
    symbol: str,
    latest: Mapping[str, Any],
    active: ActiveMRZ | None,
    window_counts: Mapping[str, Any],
    concentration_checks: Mapping[Route, ConcentrationDiagnostic] | None,
    migration: Mapping[str, Any],
    operator_promotion: Mapping[str, Any] | None,
    production_confirmation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    base = {
        "symbol": symbol,
        "latest_observation_price": number(latest["observation_price"]),
        "latest_observed_at": iso(latest["observed_at"]),
        "latest_observation_route": str(latest["route"]),
        "latest_observation_type": str(latest["observation_type"]),
        "current_price_location": current_price_location_value(latest),
        "current_location_context": ipda_directional_context(
            Decimal(latest["observation_price"]),
            Decimal(latest["ipda_20w_high"]),
            Decimal(latest["ipda_20w_low"]),
        ),
        "btd_window_observation_count": int(window_counts["btd_window_observation_count"]),
        "btd_window_started_at": iso(window_counts["btd_window_started_at"]),
        "str_window_observation_count": int(window_counts["str_window_observation_count"]),
        "str_window_started_at": iso(window_counts["str_window_started_at"]),
        "concentration_checks": (
            {
                route.value: concentration_diagnostic_payload(concentration_checks[route])
                for route in Route
            }
            if concentration_checks is not None
            else None
        ),
        "migration": dict(migration),
        "operator_promotion": (
            dict(operator_promotion) if operator_promotion is not None else None
        ),
        "production_confirmation": (
            dict(production_confirmation)
            if production_confirmation is not None
            else None
        ),
    }
    if active is None:
        return {
            **base,
            "mrz_status": "unestablished",
            "route_owner": None,
            "core_mrz_lower": None,
            "core_mrz_upper": None,
            "core_mrz_midpoint": None,
            "structural_location": None,
            "confirming_observation_count": None,
            "supporting_observation_count": None,
            "activated_at": None,
            "activation_event_id": None,
            "activation_source": None,
            "formation_started_at": None,
            "formation_completed_at": None,
            "formation_duration_seconds": None,
        }
    return {
        **base,
        "mrz_status": "active",
        "route_owner": active.route_owner.value,
        "core_mrz_lower": number(active.core_mrz_lower),
        "core_mrz_upper": number(active.core_mrz_upper),
        "core_mrz_midpoint": number(active.core_mrz_midpoint),
        "structural_location": active.structural_location.value,
        "confirming_observation_count": active.confirming_observation_count,
        "supporting_observation_count": active.supporting_observation_count,
        "activated_at": iso(active.activated_at),
        "activation_event_id": active.activation_event_id,
        "activation_source": active.activation_source.value,
        "formation_started_at": iso(active.formation_started_at),
        "formation_completed_at": iso(active.formation_completed_at),
        "formation_duration_seconds": number(active.formation_duration_seconds),
        "ipda_20w_high_at_activation": number(active.ipda_20w_high_at_activation),
        "ipda_20w_low_at_activation": number(active.ipda_20w_low_at_activation),
        "ipda_width_at_activation": number(active.ipda_width_at_activation),
        "normalized_span_at_activation": number(active.normalized_span_at_activation),
        "lower_migration_boundary": number(active.lower_migration_boundary),
        "upper_migration_boundary": number(active.upper_migration_boundary),
    }


def current_price_location_value(latest: Mapping[str, Any]) -> str | None:
    location = classify_ipda_location(
        Decimal(latest["observation_price"]),
        Decimal(latest["ipda_20w_high"]),
        Decimal(latest["ipda_20w_low"]),
    )
    return location.value if location else None


def sanitize_payload(value: Any) -> Any:
    secret_keys = {"webhook_secret", "secret", "authorization", "token", "api_key"}
    if isinstance(value, Mapping):
        return {
            str(key): ("[REDACTED]" if str(key).lower() in secret_keys else sanitize_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def json_diagnostics(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))
