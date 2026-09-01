from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlsplit

from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pywebpush import WebPushException, webpush

from app.config import Settings
from app.db import connect, transaction


LOGGER = logging.getLogger("edge2.notifications")
PERMANENT_SUBSCRIPTION_FAILURES = {404, 410}
MAX_DELIVERY_ATTEMPTS = 3
RETRYABLE_PROVIDER_FAILURES = {408, 425, 429}
STRUCTURAL_LOCATION_LABELS = {
    "deep_discount_core_mrz": "Deep Discount",
    "shallow_discount_core_mrz": "Shallow Discount",
    "shallow_premium_core_mrz": "Shallow Premium",
    "deep_premium_core_mrz": "Deep Premium",
}


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

    def reconcile_activated_events(self, trigger_event_id: str | None = None) -> list[int]:
        query = """
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
                deliverable
            )
            SELECT
                event_key,
                trigger_event_id,
                event_type,
                symbol,
                route_owner,
                structural_location,
                new_core_mrz_lower,
                new_core_mrz_upper,
                occurred_at,
                TRUE
            FROM mrz_events
            WHERE event_type = 'MRZ_ACTIVATED'
        """
        parameters: tuple[Any, ...] = ()
        if trigger_event_id is not None:
            query += " AND trigger_event_id = %s"
            parameters = (trigger_event_id,)
        query += " ON CONFLICT (source_event_key) DO NOTHING RETURNING id"

        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return [int(row[0]) for row in cursor.fetchall()]

    def latest_notification_id(self) -> int:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(id), 0)
                    FROM web_push_notifications
                    WHERE deliverable = TRUE
                      AND event_type = 'MRZ_ACTIVATED'
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
                      AND event_type = 'MRZ_ACTIVATED'
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
                      AND n.event_type = 'MRZ_ACTIVATED'
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
        sender: Callable[..., Any] = webpush,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sender = sender

    @property
    def web_push_configured(self) -> bool:
        return bool(
            self.settings.web_push_vapid_public_key
            and self.settings.web_push_vapid_private_key
            and self.settings.web_push_vapid_subject
        )

    def process_trigger_event(self, trigger_event_id: str) -> None:
        self.repository.reconcile_activated_events(trigger_event_id)
        # Each accepted or duplicate webhook is a lightweight opportunity to
        # resume persisted transient deliveries. Claiming remains atomic and
        # bounded, so this sweep cannot resend successes or create new logical
        # notifications.
        self.dispatch_pending()

    def recover(self) -> None:
        self.repository.reconcile_activated_events()
        self.dispatch_pending()

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
    structural_location = str(row["structural_location"])
    lower = decimal_text(row["core_mrz_lower"])
    upper = decimal_text(row["core_mrz_upper"])
    location_label = STRUCTURAL_LOCATION_LABELS.get(structural_location, structural_location)
    event_key = str(row["source_event_key"])
    return {
        "version": 1,
        "event_type": "MRZ_ACTIVATED",
        "event_id": event_key,
        "title": "EDGE MRZ",
        "body": (
            f"{symbol} · {route_owner} MRZ activated\n"
            f"{location_label} · {lower}–{upper}"
        ),
        "symbol": symbol,
        "route_owner": route_owner,
        "structural_location": structural_location,
        "mrz_lower": lower,
        "mrz_upper": upper,
        "activated_at": iso(row["activated_at"]),
        "url": f"/?symbol={quote(symbol, safe='')}",
    }


def decimal_text(value: Any) -> str:
    decimal_value = Decimal(value)
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def iso(value: Any) -> str:
    return value.isoformat().replace("+00:00", "Z")
