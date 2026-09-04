from __future__ import annotations

import os
import unittest

from app.db import apply_migrations, transaction


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()


def require_test_database(_test_case: object) -> str:
    if not TEST_DATABASE_URL:
        raise unittest.SkipTest("TEST_DATABASE_URL is not configured")
    return TEST_DATABASE_URL


def migrate_and_clean(database_url: str) -> None:
    apply_migrations(database_url)
    clean(database_url)


def clean(database_url: str) -> None:
    with transaction(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE TABLE
                    saved_symbol_groups,
                    web_push_delivery_attempts,
                    web_push_notifications,
                    web_push_subscriptions,
                    current_production_near_miss_episodes,
                    mrz_production_confirmations,
                    mrz_events,
                    active_mrz,
                    operator_mrz_promotions,
                    observations,
                    ingestion_rejections
                RESTART IDENTITY CASCADE
                """
            )
            cursor.execute(
                """
                UPDATE ingestion_metrics
                SET accepted_payload_count = 0,
                    rejected_payload_count = 0,
                    duplicate_payload_count = 0,
                    latest_accepted_webhook_at = NULL
                WHERE singleton = TRUE
                """
            )
