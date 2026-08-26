from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from psycopg2.extras import Json, RealDictCursor

from app.concentration import (
    ROUTE_OBSERVATION_WINDOW,
    ConcentrationDiagnostic,
    ConcentrationResult,
    evaluate_concentration,
)
from app.db import connect, transaction
from app.domain import (
    ActiveMRZ,
    MRZTransition,
    Observation,
    ObservationType,
    ReplayResult,
    Route,
    StructuralLocation,
)
from app.feasibility import build_feasibility_report
from app.state_engine import replay_symbol
from app.structure import classify_ipda_location, ipda_directional_context
from app.validation import ObservationPayload, normalize_symbol


LOGGER = logging.getLogger("edge2.repository")


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    accepted: bool
    duplicate: bool
    event_id: str
    symbol: str
    replay: ReplayResult | None
    triggered_transitions: tuple[MRZTransition, ...]


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
            occurred_at, trigger_event_id, route_owner,
            old_core_mrz_lower, old_core_mrz_upper,
            new_core_mrz_lower, new_core_mrz_upper, new_core_mrz_midpoint
        FROM mrz_events
        WHERE symbol = %s
          AND event_type = 'MRZ_MIGRATED'
          AND trigger_event_id = %s
          AND occurred_at = %s
          AND route_owner = %s
          AND new_core_mrz_lower = %s
          AND new_core_mrz_upper = %s
          AND new_core_mrz_midpoint = %s
        ORDER BY sequence DESC
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


class EdgeRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def ingest(self, payload: ObservationPayload, price_tick: Decimal) -> IngestionOutcome:
        raw_payload = payload.model_dump(mode="json", exclude={"webhook_secret"})
        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (payload.symbol,))
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
                replay = replay_symbol([observation_from_row(row) for row in cursor.fetchall()])
                self._replace_derived_state(cursor, replay)
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
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
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
                activated_at, activation_event_id,
                formation_started_at, formation_completed_at,
                formation_duration_seconds,
                ipda_20w_high_at_activation, ipda_20w_low_at_activation,
                ipda_width_at_activation, normalized_span_at_activation,
                instrument_tick, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
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
                        e.new_core_mrz_midpoint
                    FROM mrz_events e
                    INNER JOIN active_mrz a
                        ON a.symbol = e.symbol
                       AND a.activation_event_id = e.trigger_event_id
                       AND a.activated_at = e.occurred_at
                       AND a.route_owner = e.route_owner
                       AND a.core_mrz_lower = e.new_core_mrz_lower
                       AND a.core_mrz_upper = e.new_core_mrz_upper
                       AND a.core_mrz_midpoint = e.new_core_mrz_midpoint
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

    def trading_window_feasibility_report(self) -> dict[str, Any]:
        """Build the research-only report from a consistent persisted snapshot."""
        connection = connect(self.database_url)
        try:
            connection.set_session(
                readonly=True,
                isolation_level="REPEATABLE READ",
            )
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id, event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low, observed_at, received_at
                    FROM observations
                    WHERE schema_version = '4.3'
                    ORDER BY symbol ASC, observed_at ASC, received_at ASC, id ASC
                    """
                )
                observations = tuple(
                    observation_from_row(row) for row in cursor.fetchall()
                )
                cursor.execute(
                    """
                    SELECT symbol, sequence, event_type, trigger_event_id
                    FROM mrz_events
                    ORDER BY symbol ASC, sequence ASC
                    """
                )
                events = tuple(dict(row) for row in cursor.fetchall())
                cursor.execute("SELECT * FROM active_mrz ORDER BY symbol ASC")
                active_rows = tuple(
                    active
                    for active in (
                        active_from_row(row) for row in cursor.fetchall()
                    )
                    if active is not None
                )
                return build_feasibility_report(
                    observations,
                    events,
                    active_rows,
                )
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
                        o.symbol, o.observation_price,
                        o.ipda_20w_high, o.ipda_20w_low, o.observed_at,
                        a.route_owner, a.core_mrz_lower, a.core_mrz_upper,
                        a.core_mrz_midpoint, a.structural_location,
                        a.confirming_observation_count,
                        c.btd_window_observation_count,
                        c.str_window_observation_count
                    FROM latest_observations o
                    LEFT JOIN active_mrz a ON a.symbol = o.symbol
                    LEFT JOIN LATERAL (
                        SELECT
                            (
                                SELECT COUNT(*)
                                FROM (
                                    SELECT id
                                    FROM observations
                                    WHERE symbol = o.symbol AND route = 'BTD'
                                    ORDER BY observed_at DESC, received_at DESC, id DESC
                                    LIMIT %s
                                ) AS btd_window
                            ) AS btd_window_observation_count,
                            (
                                SELECT COUNT(*)
                                FROM (
                                    SELECT id
                                    FROM observations
                                    WHERE symbol = o.symbol AND route = 'STR'
                                    ORDER BY observed_at DESC, received_at DESC, id DESC
                                    LIMIT %s
                                ) AS str_window
                            ) AS str_window_observation_count
                    ) c ON TRUE
                    ORDER BY o.symbol ASC
                    """,
                    (ROUTE_OBSERVATION_WINDOW, ROUTE_OBSERVATION_WINDOW),
                )
                return [
                    {
                        "symbol": row["symbol"],
                        "mrz_status": "active" if row["route_owner"] else "unestablished",
                        "route_owner": row["route_owner"],
                        "core_mrz_lower": number(row["core_mrz_lower"]),
                        "core_mrz_upper": number(row["core_mrz_upper"]),
                        "core_mrz_midpoint": number(row["core_mrz_midpoint"]),
                        "structural_location": row["structural_location"],
                        "confirming_observation_count": row["confirming_observation_count"],
                        "latest_observation_price": number(row["observation_price"]),
                        "latest_observed_at": iso(row["observed_at"]),
                        "current_price_location": current_price_location_value(row),
                        "btd_window_observation_count": int(row["btd_window_observation_count"]),
                        "str_window_observation_count": int(row["str_window_observation_count"]),
                    }
                    for row in cursor.fetchall()
                ]
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


def detail_payload(
    symbol: str,
    latest: Mapping[str, Any],
    active: ActiveMRZ | None,
    window_counts: Mapping[str, Any],
    concentration_checks: Mapping[Route, ConcentrationDiagnostic] | None,
    migration: Mapping[str, Any],
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
