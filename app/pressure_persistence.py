from __future__ import annotations

import hashlib
from typing import Sequence

from psycopg2.extras import Json, RealDictCursor

from app.domain import ActiveMRZ, Observation
from app.mrz_robustness import decimal_text, iso, post_activation_snapshot
from app.pressure import (
    CURRENT_PRESSURE_CONFIRMATION_COUNT,
    CURRENT_PRESSURE_RECENT_WINDOW,
)


class CurrentPressurePersistence:
    """Pressure-only state and transition writes within the ingestion transaction."""

    def synchronize(
        self,
        cursor: RealDictCursor,
        *,
        active: ActiveMRZ,
        observations: Sequence[Observation],
        trigger: Observation,
        emit_event: bool,
    ) -> bool:
        snapshot = post_activation_snapshot(active, observations)
        current = snapshot.current_pressure
        state = current.state
        evidence = current.recent_evidence
        cursor.execute(
            """
            SELECT * FROM current_pressure_states
            WHERE symbol = %s AND lifecycle_activation_event_id = %s
            FOR UPDATE
            """,
            (active.symbol, active.activation_event_id),
        )
        previous = cursor.fetchone()
        if previous is None:
            cursor.execute(
                """
                INSERT INTO current_pressure_states (
                    symbol, lifecycle_activation_event_id, current_state,
                    state_status, state_label,
                    recent_pressure_observation_count,
                    recent_higher_observation_count,
                    recent_lower_observation_count,
                    last_evaluated_trigger_event_id,
                    last_evaluated_observation_id,
                    last_evaluated_received_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    active.symbol,
                    active.activation_event_id,
                    state.direction,
                    state.status,
                    state.label,
                    len(evidence),
                    current.recent_higher_count,
                    current.recent_lower_count,
                    trigger.event_id,
                    trigger.id,
                    trigger.received_at,
                ),
            )
            return False

        previous_state = str(previous["current_state"])
        changed = previous_state != state.direction
        if changed and emit_event:
            event_key_source = "|".join(
                (
                    active.symbol,
                    active.activation_event_id,
                    trigger.event_id,
                    previous_state,
                    state.direction,
                )
            )
            event_key = "CURRENT_PRESSURE_CHANGED:" + hashlib.sha256(
                event_key_source.encode("utf-8")
            ).hexdigest()
            supporting = [
                {
                    "event_id": item.observation.event_id,
                    "direction": item.direction,
                    "direction_label": "Higher" if item.direction == "UP" else "Lower",
                    "route": item.observation.route.value,
                    "observation_type": item.observation.observation_type.value,
                    "observation_price": decimal_text(item.observation.observation_price),
                    "observed_at": iso(item.observation.observed_at),
                    "received_at": iso(item.observation.received_at),
                }
                for item in evidence
            ]
            cursor.execute(
                """
                INSERT INTO current_pressure_events (
                    event_key, symbol, lifecycle_activation_event_id,
                    trigger_event_id, trigger_observation_id, route_owner,
                    previous_state, current_state, state_status, state_label,
                    occurred_at, supporting_observed_at,
                    recent_pressure_observation_count,
                    recent_higher_observation_count,
                    recent_lower_observation_count,
                    recent_window_size, confirmation_count,
                    lower_migration_boundary, upper_migration_boundary,
                    supporting_observations
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (event_key) DO NOTHING
                """,
                (
                    event_key,
                    active.symbol,
                    active.activation_event_id,
                    trigger.event_id,
                    trigger.id,
                    active.route_owner.value,
                    previous_state,
                    state.direction,
                    state.status,
                    state.label,
                    trigger.received_at,
                    current.latest_pressure_observed_at,
                    len(evidence),
                    current.recent_higher_count,
                    current.recent_lower_count,
                    CURRENT_PRESSURE_RECENT_WINDOW,
                    CURRENT_PRESSURE_CONFIRMATION_COUNT,
                    active.lower_migration_boundary,
                    active.upper_migration_boundary,
                    Json(supporting),
                ),
            )

        cursor.execute(
            """
            UPDATE current_pressure_states
            SET current_state = %s,
                state_status = %s,
                state_label = %s,
                recent_pressure_observation_count = %s,
                recent_higher_observation_count = %s,
                recent_lower_observation_count = %s,
                transition_count = transition_count + %s,
                last_evaluated_trigger_event_id = %s,
                last_evaluated_observation_id = %s,
                last_evaluated_received_at = %s,
                updated_at = clock_timestamp()
            WHERE symbol = %s AND lifecycle_activation_event_id = %s
            """,
            (
                state.direction,
                state.status,
                state.label,
                len(evidence),
                current.recent_higher_count,
                current.recent_lower_count,
                1 if changed else 0,
                trigger.event_id,
                trigger.id,
                trigger.received_at,
                active.symbol,
                active.activation_event_id,
            ),
        )
        return changed and emit_event
