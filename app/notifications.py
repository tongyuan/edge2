from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlsplit

from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pywebpush import WebPushException, webpush

from app.config import Settings
from app.db import connect, transaction
from app.mrz_robustness import MRZRobustnessService, RobustnessInputProvider


LOGGER = logging.getLogger("edge2.notifications")
PERMANENT_SUBSCRIPTION_FAILURES = {404, 410}
MAX_DELIVERY_ATTEMPTS = 3
RETRYABLE_PROVIDER_FAILURES = {408, 425, 429}
PRESSURE_EVENT_TYPE = "POST_ACTIVATION_PRESSURE_CHANGED"
PRESSURE_DIRECTIONS = {"UP", "DOWN"}


def should_notify_pressure_transition(previous_state: str, current_state: str) -> bool:
    """Return whether a persisted state change enters directional pressure."""
    return previous_state != current_state and current_state in PRESSURE_DIRECTIONS


class PushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    p256dh: str = Field(min_length=40, max_length=512, pattern=r"^[A-Za-z0-9_-]+={0,2}$")
    auth: str = Field(min_length=8, max_length=256, pattern=r"^[A-Za-z0-9_-]+={0,2}$")


class PushSubscriptionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint: str = Field(min_length=12, max_length=4096)
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("endpoint must be an absolute HTTPS URL")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("endpoint must not contain credentials or a fragment")
        return value


class PushSubscriptionDelete(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint: str = Field(min_length=12, max_length=4096)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        return PushSubscriptionPayload.validate_endpoint(value)


class NotificationRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def upsert_subscription(self, subscription: PushSubscriptionPayload) -> dict[str, Any]:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO web_push_subscriptions (endpoint, p256dh, auth)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (endpoint) DO UPDATE SET
                        p256dh = EXCLUDED.p256dh,
                        auth = EXCLUDED.auth,
                        enabled_at = CASE
                            WHEN web_push_subscriptions.enabled
                                THEN web_push_subscriptions.enabled_at
                            WHEN web_push_subscriptions.disabled_reason = 'expired'
                              AND web_push_subscriptions.p256dh = EXCLUDED.p256dh
                              AND web_push_subscriptions.auth = EXCLUDED.auth
                                THEN web_push_subscriptions.enabled_at
                            ELSE clock_timestamp()
                        END,
                        enabled = NOT COALESCE((
                            web_push_subscriptions.disabled_reason = 'expired'
                            AND web_push_subscriptions.p256dh = EXCLUDED.p256dh
                            AND web_push_subscriptions.auth = EXCLUDED.auth
                        ), FALSE),
                        disabled_reason = CASE
                            WHEN web_push_subscriptions.disabled_reason = 'expired'
                              AND web_push_subscriptions.p256dh = EXCLUDED.p256dh
                              AND web_push_subscriptions.auth = EXCLUDED.auth
                                THEN 'expired'
                            ELSE NULL
                        END,
                        updated_at = clock_timestamp(),
                        failure_count = 0
                    RETURNING id, enabled, disabled_reason
                    """,
                    (
                        subscription.endpoint,
                        subscription.keys.p256dh,
                        subscription.keys.auth,
                    ),
                )
                row = cursor.fetchone()
                return {
                    "id": int(row[0]),
                    "enabled": bool(row[1]),
                    "disabled_reason": row[2],
                }

    def disable_subscription(self, endpoint: str) -> bool:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE web_push_subscriptions
                    SET enabled = FALSE, disabled_reason = 'operator',
                        updated_at = clock_timestamp()
                    WHERE endpoint = %s AND enabled = TRUE
                    """,
                    (endpoint,),
                )
                return cursor.rowcount > 0

    def reconcile_pressure_state(
        self,
        report: Mapping[str, Any],
        evaluation_trigger_event_id: str,
    ) -> int | None:
        """Persist one lifecycle-scoped pressure comparison and optional outbox row."""
        symbol = str(report["symbol"])
        active = report["active_mrz"]
        pressure = report["migration_pressure"]
        position = report["observation_position"]
        boundary = report["boundary_pressure"]
        displacement = report["mrz_displacement"]
        successor = report["successor_watch"]
        activation_event_id = str(active["activation_event_id"])
        current_state = str(pressure["direction"])
        if current_state not in {"NEUTRAL", *PRESSURE_DIRECTIONS}:
            raise ValueError(f"Unsupported post-activation direction: {current_state}")

        with transaction(self.database_url) as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"POST_ACTIVATION_PRESSURE:{symbol}",),
                )
                cursor.execute(
                    """
                    SELECT activation_event_id
                    FROM active_mrz
                    WHERE symbol = %s
                    """,
                    (symbol,),
                )
                current_authority = cursor.fetchone()
                if (
                    current_authority is None
                    or str(current_authority["activation_event_id"])
                    != activation_event_id
                ):
                    return None

                cursor.execute(
                    """
                    SELECT id, event_id, received_at
                    FROM observations
                    WHERE symbol = %s
                    ORDER BY received_at DESC, id DESC
                    LIMIT 1
                    """,
                    (symbol,),
                )
                latest_observation = cursor.fetchone()
                if (
                    latest_observation is None
                    or str(latest_observation["event_id"])
                    != evaluation_trigger_event_id
                ):
                    # A newer canonical packet committed after the report snapshot.
                    # Its own background task or startup recovery will evaluate it.
                    return None

                cursor.execute(
                    """
                    SELECT *
                    FROM post_activation_pressure_states
                    WHERE symbol = %s AND activation_event_id = %s
                    FOR UPDATE
                    """,
                    (symbol, activation_event_id),
                )
                previous = cursor.fetchone()
                evaluation_order = (
                    latest_observation["received_at"],
                    int(latest_observation["id"]),
                )
                if previous is not None:
                    previous_order = (
                        previous["last_evaluated_received_at"],
                        int(previous["last_evaluated_observation_id"]),
                    )
                    if previous_order >= evaluation_order:
                        return None

                cursor.execute(
                    """
                    SELECT enabled_at
                    FROM web_push_notification_cutovers
                    WHERE event_type = %s
                    """,
                    (PRESSURE_EVENT_TYPE,),
                )
                cutover_row = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT COALESCE(
                        (
                            SELECT promoted_at
                            FROM operator_mrz_promotions
                            WHERE symbol = %s AND trigger_event_id = %s
                        ),
                        (
                            SELECT received_at
                            FROM observations
                            WHERE event_id = %s
                        )
                    ) AS lifecycle_started_at
                    """,
                    (symbol, activation_event_id, activation_event_id),
                )
                lifecycle_row = cursor.fetchone()
                lifecycle_started_at = lifecycle_row["lifecycle_started_at"]
                lifecycle_is_live = bool(
                    cutover_row is not None
                    and lifecycle_started_at is not None
                    and lifecycle_started_at >= cutover_row["enabled_at"]
                )

                previous_state = (
                    str(previous["current_state"])
                    if previous is not None
                    else "NEUTRAL"
                    if lifecycle_is_live
                    else current_state
                )
                state_changed = previous_state != current_state
                transition_count = (
                    int(previous["transition_count"]) if previous is not None else 0
                ) + int(state_changed)
                cursor.execute("SELECT clock_timestamp() AS evaluated_at")
                evaluated_at = cursor.fetchone()["evaluated_at"]
                metrics = (
                    int(position["total_observation_count"]),
                    int(position["above_active_mrz_observation_count"]),
                    int(position["inside_active_mrz_observation_count"]),
                    int(position["below_active_mrz_observation_count"]),
                    int(boundary["above_upper_envelope_observation_count"]),
                    int(boundary["below_lower_envelope_observation_count"]),
                )
                displacement_value = displacement[
                    "median_signed_displacement_percentage_of_activation_ipda"
                ]
                cursor.execute(
                    """
                    INSERT INTO post_activation_pressure_states (
                        symbol, activation_event_id, current_state,
                        state_status, state_label,
                        post_activation_observation_count,
                        above_mrz_count, inside_mrz_count, below_mrz_count,
                        above_envelope_count, below_envelope_count,
                        displacement, successor_status, successor_label,
                        transition_count, last_evaluated_trigger_event_id,
                        last_evaluated_observation_id,
                        last_evaluated_received_at, last_evaluated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (symbol, activation_event_id) DO UPDATE SET
                        current_state = EXCLUDED.current_state,
                        state_status = EXCLUDED.state_status,
                        state_label = EXCLUDED.state_label,
                        post_activation_observation_count =
                            EXCLUDED.post_activation_observation_count,
                        above_mrz_count = EXCLUDED.above_mrz_count,
                        inside_mrz_count = EXCLUDED.inside_mrz_count,
                        below_mrz_count = EXCLUDED.below_mrz_count,
                        above_envelope_count = EXCLUDED.above_envelope_count,
                        below_envelope_count = EXCLUDED.below_envelope_count,
                        displacement = EXCLUDED.displacement,
                        successor_status = EXCLUDED.successor_status,
                        successor_label = EXCLUDED.successor_label,
                        transition_count = EXCLUDED.transition_count,
                        last_evaluated_trigger_event_id =
                            EXCLUDED.last_evaluated_trigger_event_id,
                        last_evaluated_observation_id =
                            EXCLUDED.last_evaluated_observation_id,
                        last_evaluated_received_at =
                            EXCLUDED.last_evaluated_received_at,
                        last_evaluated_at = EXCLUDED.last_evaluated_at,
                        updated_at = clock_timestamp()
                    """,
                    (
                        symbol,
                        activation_event_id,
                        current_state,
                        str(pressure["status"]),
                        str(pressure["label"]),
                        *metrics,
                        displacement_value,
                        str(successor["status"]),
                        str(successor["label"]),
                        transition_count,
                        evaluation_trigger_event_id,
                        int(latest_observation["id"]),
                        latest_observation["received_at"],
                        evaluated_at,
                    ),
                )

                if not should_notify_pressure_transition(
                    previous_state,
                    current_state,
                ):
                    return None

                source_event_key = (
                    f"{PRESSURE_EVENT_TYPE}:{symbol}:{activation_event_id}:"
                    f"{evaluation_trigger_event_id}:{current_state}"
                )
                cursor.execute(
                    """
                    INSERT INTO web_push_notifications (
                        source_event_key, source_trigger_event_id, event_type,
                        symbol, route_owner, structural_location,
                        core_mrz_lower, core_mrz_upper, activated_at, occurred_at,
                        lifecycle_activation_event_id,
                        previous_pressure_state, current_pressure_state,
                        pressure_state_label,
                        post_activation_observation_count,
                        above_mrz_count, inside_mrz_count, below_mrz_count,
                        above_envelope_count, below_envelope_count,
                        displacement, successor_status, successor_label,
                        deliverable
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, TRUE
                    )
                    ON CONFLICT (source_event_key) DO NOTHING
                    RETURNING id
                    """,
                    (
                        source_event_key,
                        evaluation_trigger_event_id,
                        PRESSURE_EVENT_TYPE,
                        symbol,
                        str(report["route_owner"]),
                        str(report["structural_authority"]["structural_location"]),
                        active["lower"],
                        active["upper"],
                        active["activated_at"],
                        evaluated_at,
                        activation_event_id,
                        previous_state,
                        current_state,
                        str(pressure["label"]),
                        *metrics,
                        displacement_value,
                        str(successor["status"]),
                        str(successor["label"]),
                    ),
                )
                inserted = cursor.fetchone()
                return int(inserted["id"]) if inserted is not None else None

    def reconcile_notifiable_events(self, trigger_event_id: str | None = None) -> list[int]:
        authority_query = """
            INSERT INTO web_push_notifications (
                source_event_key,
                source_trigger_event_id,
                source_event_sequence,
                event_type,
                symbol,
                route_owner,
                previous_route_owner,
                structural_location,
                previous_core_mrz_lower,
                previous_core_mrz_upper,
                core_mrz_lower,
                core_mrz_upper,
                activated_at,
                occurred_at,
                deliverable
            )
            SELECT
                e.event_key,
                e.trigger_event_id,
                e.sequence,
                e.event_type,
                e.symbol,
                e.route_owner,
                e.previous_route_owner,
                e.structural_location,
                e.old_core_mrz_lower,
                e.old_core_mrz_upper,
                e.new_core_mrz_lower,
                e.new_core_mrz_upper,
                e.occurred_at,
                e.occurred_at,
                TRUE
            FROM mrz_events e
            INNER JOIN observations o
                ON o.event_id = e.trigger_event_id
            LEFT JOIN web_push_notification_cutovers c
                ON c.event_type = e.event_type
            WHERE e.event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')
              AND (
                  e.event_type = 'MRZ_ACTIVATED'
                  OR o.received_at >= c.enabled_at
              )
        """
        parameters: tuple[Any, ...] = ()
        if trigger_event_id is not None:
            authority_query += " AND e.trigger_event_id = %s"
            parameters = (trigger_event_id,)
        authority_query += " ON CONFLICT (source_event_key) DO NOTHING RETURNING id"

        near_miss_query = """
            INSERT INTO web_push_notifications (
                source_event_key,
                source_trigger_event_id,
                event_type,
                symbol,
                route_owner,
                structural_location,
                core_mrz_lower,
                core_mrz_upper,
                activated_at,
                occurred_at,
                candidate_identity,
                evaluator_identity,
                minimum_required_allowance_pct,
                production_threshold_pct,
                shortfall_percentage_points,
                supporting_observation_count,
                candidate_timestamp,
                deliverable
            )
            SELECT
                episode_key,
                source_trigger_event_id,
                'MRZ_NEAR_MISS',
                symbol,
                route_owner,
                structural_location,
                candidate_lower,
                candidate_upper,
                candidate_timestamp,
                started_at,
                candidate_identity,
                evaluator_identity,
                minimum_required_allowance_pct,
                production_threshold_pct,
                shortfall_percentage_points,
                supporting_observation_count,
                candidate_timestamp,
                TRUE
            FROM current_production_near_miss_episodes
            WHERE deliverable = TRUE
        """
        if trigger_event_id is not None:
            near_miss_query += " AND source_trigger_event_id = %s"
        near_miss_query += (
            " ON CONFLICT (source_event_key) DO NOTHING RETURNING id"
        )

        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(authority_query, parameters)
                notification_ids = [int(row[0]) for row in cursor.fetchall()]
                cursor.execute(near_miss_query, parameters)
                notification_ids.extend(int(row[0]) for row in cursor.fetchall())
                return notification_ids

    def latest_notification_id(self) -> int:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(id), 0)
                    FROM web_push_notifications
                    WHERE deliverable = TRUE
                      AND event_type IN (
                          'MRZ_ACTIVATED', 'MRZ_MIGRATED', 'MRZ_NEAR_MISS',
                          'POST_ACTIVATION_PRESSURE_CHANGED'
                      )
                    """
                )
                return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def site_events_after(self, after_id: int, limit: int = 10) -> list[dict[str, Any]]:
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM web_push_notifications
                    WHERE deliverable = TRUE
                      AND event_type IN (
                          'MRZ_ACTIVATED', 'MRZ_MIGRATED', 'MRZ_NEAR_MISS',
                          'POST_ACTIVATION_PRESSURE_CHANGED'
                      )
                      AND id > %s
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (after_id, limit),
                )
                return [
                    {"id": int(row["id"]), **notification_payload(row)}
                    for row in cursor.fetchall()
                ]
        finally:
            connection.close()

    def pending_deliveries(
        self,
        notification_ids: Sequence[int] | None = None,
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = []
        notification_filter = ""
        if notification_ids is not None:
            if not notification_ids:
                return []
            notification_filter = " AND n.id = ANY(%s)"
            parameters.append(list(notification_ids))

        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        n.*,
                        s.id AS subscription_id,
                        s.endpoint,
                        s.p256dh,
                        s.auth
                    FROM web_push_notifications n
                    CROSS JOIN web_push_subscriptions s
                    LEFT JOIN LATERAL (
                        SELECT
                            COUNT(*) AS attempt_count,
                            COUNT(*) FILTER (
                                WHERE d.outcome = 'DELIVERED'
                            ) AS delivered_count,
                            COUNT(*) FILTER (
                                WHERE d.outcome = 'CLAIMED'
                            ) AS claimed_count,
                            (ARRAY_AGG(
                                d.retryable ORDER BY d.attempt_number DESC
                            ))[1] AS last_retryable
                        FROM web_push_delivery_attempts d
                        WHERE d.notification_id = n.id
                          AND d.subscription_id = s.id
                    ) attempts ON TRUE
                    WHERE n.deliverable = TRUE
                      AND n.event_type IN (
                          'MRZ_ACTIVATED', 'MRZ_MIGRATED', 'MRZ_NEAR_MISS',
                          'POST_ACTIVATION_PRESSURE_CHANGED'
                      )
                      AND s.enabled = TRUE
                      AND s.enabled_at <= n.created_at
                      AND attempts.attempt_count < {MAX_DELIVERY_ATTEMPTS}
                      AND attempts.delivered_count = 0
                      AND attempts.claimed_count = 0
                      AND (
                          attempts.attempt_count = 0
                          OR attempts.last_retryable IS TRUE
                      )
                      {notification_filter}
                    ORDER BY n.id ASC, s.id ASC
                    """,
                    parameters,
                )
                return [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def claim_delivery(self, notification_id: int, subscription_id: int) -> int | None:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH attempt_summary AS (
                        SELECT
                            COALESCE(MAX(attempt_number), 0) AS max_attempt,
                            COUNT(*) FILTER (
                                WHERE outcome = 'DELIVERED'
                            ) AS delivered_count,
                            COUNT(*) FILTER (
                                WHERE outcome = 'CLAIMED'
                            ) AS claimed_count,
                            (ARRAY_AGG(
                                retryable ORDER BY attempt_number DESC
                            ))[1] AS last_retryable
                        FROM web_push_delivery_attempts
                        WHERE notification_id = %s
                          AND subscription_id = %s
                    )
                    INSERT INTO web_push_delivery_attempts (
                        notification_id,
                        subscription_id,
                        attempt_number,
                        outcome,
                        retryable
                    )
                    SELECT %s, %s, max_attempt + 1, 'CLAIMED', FALSE
                    FROM attempt_summary
                    WHERE max_attempt < %s
                      AND delivered_count = 0
                      AND claimed_count = 0
                      AND (max_attempt = 0 OR last_retryable IS TRUE)
                    ON CONFLICT (
                        notification_id, subscription_id, attempt_number
                    ) DO NOTHING
                    RETURNING id
                    """,
                    (
                        notification_id,
                        subscription_id,
                        notification_id,
                        subscription_id,
                        MAX_DELIVERY_ATTEMPTS,
                    ),
                )
                row = cursor.fetchone()
                return int(row[0]) if row else None

    def record_delivery_success(self, attempt_id: int, subscription_id: int) -> None:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE web_push_delivery_attempts
                    SET outcome = 'DELIVERED', completed_at = clock_timestamp(),
                        http_status = NULL, error_code = NULL
                    WHERE id = %s AND outcome = 'CLAIMED'
                    """,
                    (attempt_id,),
                )
                cursor.execute(
                    """
                    UPDATE web_push_subscriptions
                    SET last_success_at = clock_timestamp(), failure_count = 0,
                        updated_at = clock_timestamp()
                    WHERE id = %s
                    """,
                    (subscription_id,),
                )

    def record_delivery_failure(
        self,
        attempt_id: int,
        subscription_id: int,
        *,
        http_status: int | None,
        error_code: str,
        permanent: bool,
        retryable: bool,
    ) -> None:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE web_push_delivery_attempts
                    SET outcome = 'FAILED', completed_at = clock_timestamp(),
                        http_status = %s, error_code = %s, retryable = %s
                    WHERE id = %s AND outcome = 'CLAIMED'
                    """,
                    (http_status, error_code[:120], retryable, attempt_id),
                )
                cursor.execute(
                    """
                    UPDATE web_push_subscriptions
                    SET enabled = CASE WHEN %s THEN FALSE ELSE enabled END,
                        disabled_reason = CASE
                            WHEN %s THEN 'expired'
                            ELSE disabled_reason
                        END,
                        last_failure_at = clock_timestamp(),
                        failure_count = failure_count + 1,
                        updated_at = clock_timestamp()
                    WHERE id = %s
                    """,
                    (permanent, permanent, subscription_id),
                )


class NotificationService:
    def __init__(
        self,
        settings: Settings,
        repository: NotificationRepository,
        pressure_input_provider: RobustnessInputProvider | None = None,
        sender: Callable[..., Any] = webpush,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.pressure_input_provider = pressure_input_provider
        self.sender = sender

    @property
    def web_push_configured(self) -> bool:
        return bool(
            self.settings.web_push_vapid_public_key
            and self.settings.web_push_vapid_private_key
            and self.settings.web_push_vapid_subject
        )

    def process_trigger_event(self, trigger_event_id: str) -> None:
        self.repository.reconcile_notifiable_events(trigger_event_id)
        self.reconcile_pressure(trigger_event_id)
        # Each accepted or duplicate webhook is a lightweight opportunity to
        # resume persisted transient deliveries. Claiming remains atomic and
        # bounded, so this sweep cannot resend successes or create new logical
        # notifications.
        self.dispatch_pending()

    def recover(self) -> None:
        self.repository.reconcile_notifiable_events()
        self.reconcile_pressure()
        self.dispatch_pending()

    def reconcile_pressure(self, trigger_event_id: str | None = None) -> None:
        if self.pressure_input_provider is None:
            return
        try:
            active_mrzs, observations, migration_provenance = (
                self.pressure_input_provider()
            )
            if not active_mrzs:
                return
            observations_by_symbol: dict[str, list[Any]] = {}
            trigger_symbol = None
            for observation in observations:
                observations_by_symbol.setdefault(observation.symbol, []).append(
                    observation
                )
                if observation.event_id == trigger_event_id:
                    trigger_symbol = observation.symbol
            if trigger_event_id is not None and trigger_symbol is None:
                return

            generated_at = datetime.now(timezone.utc)
            robustness_service = MRZRobustnessService(
                lambda: (active_mrzs, observations, migration_provenance)
            )
            for active in active_mrzs:
                if trigger_symbol is not None and active.symbol != trigger_symbol:
                    continue
                symbol_observations = observations_by_symbol.get(active.symbol, [])
                if not symbol_observations:
                    continue
                evaluation_trigger = max(
                    symbol_observations,
                    key=lambda item: (item.received_at, item.id),
                )
                report = robustness_service.active_mrz_report(
                    active,
                    symbol_observations,
                    generated_at,
                    migration_provenance.get(
                        active.symbol,
                        {"has_migrated": False},
                    ),
                )
                self.repository.reconcile_pressure_state(
                    report,
                    evaluation_trigger.event_id,
                )
        except Exception:
            LOGGER.exception(
                "Post-activation pressure reconciliation failed; MRZ authority "
                "and other notifications are unaffected",
                extra={"trigger_event_id": trigger_event_id},
            )

    def dispatch_pending(self, notification_ids: Sequence[int] | None = None) -> None:
        if not self.web_push_configured:
            return
        for delivery in self.repository.pending_deliveries(notification_ids):
            notification_id = int(delivery["id"])
            subscription_id = int(delivery["subscription_id"])
            attempt_id = self.repository.claim_delivery(notification_id, subscription_id)
            if attempt_id is None:
                continue
            try:
                self.sender(
                    subscription_info={
                        "endpoint": str(delivery["endpoint"]),
                        "keys": {
                            "p256dh": str(delivery["p256dh"]),
                            "auth": str(delivery["auth"]),
                        },
                    },
                    data=json.dumps(
                        notification_payload(delivery),
                        separators=(",", ":"),
                    ),
                    vapid_private_key=self.settings.web_push_vapid_private_key,
                    vapid_claims={"sub": self.settings.web_push_vapid_subject},
                    ttl=86400,
                    timeout=5,
                )
            except WebPushException as exc:
                status = exc.status_code
                permanent = status in PERMANENT_SUBSCRIPTION_FAILURES
                retryable = not permanent and is_retryable_push_failure(status)
                self.repository.record_delivery_failure(
                    attempt_id,
                    subscription_id,
                    http_status=status,
                    error_code=(
                        "expired_subscription"
                        if permanent
                        else "transient_web_push_failure"
                        if retryable
                        else "non_retryable_web_push_failure"
                    ),
                    permanent=permanent,
                    retryable=retryable,
                )
                LOGGER.warning(
                    "Web Push delivery failed",
                    extra={
                        "notification_id": notification_id,
                        "subscription_id": subscription_id,
                        "http_status": status,
                        "permanent": permanent,
                        "retryable": retryable,
                    },
                )
            except Exception:
                self.repository.record_delivery_failure(
                    attempt_id,
                    subscription_id,
                    http_status=None,
                    error_code="transient_delivery_exception",
                    permanent=False,
                    retryable=True,
                )
                LOGGER.exception(
                    "Web Push delivery raised an exception",
                    extra={
                        "notification_id": notification_id,
                        "subscription_id": subscription_id,
                    },
                )
            else:
                self.repository.record_delivery_success(attempt_id, subscription_id)
                LOGGER.info(
                    "Web Push delivered",
                    extra={
                        "notification_id": notification_id,
                        "subscription_id": subscription_id,
                    },
                )


def is_retryable_push_failure(http_status: int | None) -> bool:
    return (
        http_status is None
        or http_status in RETRYABLE_PROVIDER_FAILURES
        or 500 <= http_status <= 599
    )


def notification_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    symbol = str(row["symbol"])
    route_owner = str(row["route_owner"])
    previous_route_owner = row.get("previous_route_owner")
    previous_route_owner = (
        str(previous_route_owner) if previous_route_owner is not None else None
    )
    structural_location = str(row["structural_location"])
    lower = decimal_text(row["core_mrz_lower"])
    upper = decimal_text(row["core_mrz_upper"])
    previous_lower_value = row.get("previous_core_mrz_lower")
    previous_upper_value = row.get("previous_core_mrz_upper")
    previous_lower = (
        decimal_text(previous_lower_value) if previous_lower_value is not None else None
    )
    previous_upper = (
        decimal_text(previous_upper_value) if previous_upper_value is not None else None
    )
    event_key = str(row["source_event_key"])
    event_type = str(row["event_type"])
    occurred_at = iso(row["occurred_at"])
    if event_type == PRESSURE_EVENT_TYPE:
        direction = str(row["current_pressure_state"])
        side = "above" if direction == "UP" else "below"
        side_mrz_count = int(row[f"{side}_mrz_count"])
        side_envelope_count = int(row[f"{side}_envelope_count"])
        title = f"{symbol} · {row['pressure_state_label']}"
        body = (
            f"Post-activation activity materially favors {side}-envelope observations · "
            f"{int(row['post_activation_observation_count'])} total · "
            f"{side_mrz_count} {side} MRZ · "
            f"{side_envelope_count} {side} envelope · {row['successor_label']}"
        )
    elif event_type == "MRZ_NEAR_MISS":
        title = f"{symbol} MRZ Near Miss"
        body = (
            f"{route_owner} · {display_decimal(row['core_mrz_lower'])}–"
            f"{display_decimal(row['core_mrz_upper'])} · Required "
            f"{Decimal(row['minimum_required_allowance_pct']):.2f}% vs "
            f"{Decimal(row['production_threshold_pct']):.2f}%"
        )
    elif event_type == "MRZ_MIGRATED":
        route_label = (
            f"{previous_route_owner} → {route_owner}"
            if previous_route_owner and previous_route_owner != route_owner
            else route_owner
        )
        title = f"{symbol} MRZ Migrated"
        body = (
            f"{route_label} · {display_decimal(previous_lower_value)}–"
            f"{display_decimal(previous_upper_value)} → "
            f"{display_decimal(row['core_mrz_lower'])}–"
            f"{display_decimal(row['core_mrz_upper'])}"
        )
    else:
        title = f"{symbol} MRZ Activated"
        body = (
            f"{route_owner} · {display_decimal(row['core_mrz_lower'])}–"
            f"{display_decimal(row['core_mrz_upper'])}"
        )

    payload = {
        "version": 1,
        "event_type": event_type,
        "event_id": event_key,
        "source_event_key": event_key,
        "source_trigger_event_id": str(row["source_trigger_event_id"]),
        "event_sequence": row.get("source_event_sequence"),
        "title": title,
        "body": body,
        "symbol": symbol,
        "route_owner": route_owner,
        "previous_route_owner": previous_route_owner,
        "structural_location": structural_location,
        "previous_mrz_lower": previous_lower,
        "previous_mrz_upper": previous_upper,
        "mrz_lower": lower,
        "mrz_upper": upper,
        "occurred_at": occurred_at,
        "url": f"/?symbol={quote(symbol, safe='')}",
    }
    if event_type == PRESSURE_EVENT_TYPE:
        displacement_value = row.get("displacement")
        payload.update({
            "lifecycle_activation_event_id": str(
                row["lifecycle_activation_event_id"]
            ),
            "previous_state": str(row["previous_pressure_state"]),
            "current_state": str(row["current_pressure_state"]),
            "pressure_state_label": str(row["pressure_state_label"]),
            "evaluated_at": occurred_at,
            "activated_at": iso(row["activated_at"]),
            "post_activation_observation_count": int(
                row["post_activation_observation_count"]
            ),
            "above_mrz_count": int(row["above_mrz_count"]),
            "inside_mrz_count": int(row["inside_mrz_count"]),
            "below_mrz_count": int(row["below_mrz_count"]),
            "above_envelope_count": int(row["above_envelope_count"]),
            "below_envelope_count": int(row["below_envelope_count"]),
            "displacement": (
                decimal_text(displacement_value)
                if displacement_value is not None
                else None
            ),
            "successor_status": str(row["successor_status"]),
            "successor_label": str(row["successor_label"]),
            "url": (
                "/diagnostics/mrz-robustness?symbol="
                f"{quote(symbol, safe='')}#post-activation"
            ),
        })
    elif event_type == "MRZ_NEAR_MISS":
        candidate_identity = str(row["candidate_identity"])
        payload.update({
            "candidate_identity": candidate_identity,
            "evaluator_identity": str(row["evaluator_identity"]),
            "candidate_lower": lower,
            "candidate_upper": upper,
            "candidate_midpoint": decimal_text(
                (Decimal(row["core_mrz_lower"]) + Decimal(row["core_mrz_upper"]))
                / Decimal("2")
            ),
            "minimum_required_allowance_pct": decimal_text(
                row["minimum_required_allowance_pct"]
            ),
            "production_threshold_pct": decimal_text(
                row["production_threshold_pct"]
            ),
            "shortfall_percentage_points": decimal_text(
                row["shortfall_percentage_points"]
            ),
            "supporting_observation_count": int(
                row["supporting_observation_count"]
            ),
            "candidate_timestamp": iso(row["candidate_timestamp"]),
            "url": (
                "/diagnostics/activation-feasibility?symbol="
                f"{quote(symbol, safe='')}&candidate="
                f"{quote(candidate_identity, safe='')}#current-production-near-misses"
            ),
        })
    elif event_type == "MRZ_ACTIVATED":
        payload["activated_at"] = occurred_at
    elif event_type == "MRZ_MIGRATED":
        payload["migrated_at"] = occurred_at
    return payload


def decimal_text(value: Any) -> str:
    decimal_value = Decimal(value)
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def display_decimal(value: Any) -> str:
    text = format(Decimal(value), ",f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def iso(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z")
