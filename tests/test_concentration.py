from __future__ import annotations

import unittest
from decimal import Decimal

from app.concentration import latest_route_window, select_cluster
from tests.helpers import observation


class ConcentrationTests(unittest.TestCase):
    def test_exactly_four_tight_observations_qualify(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.3", "110.7", "111"), 1)]
        cluster = select_cluster(rows, "event-4", Decimal("100"))
        self.assertIsNotNone(cluster)
        self.assertEqual(cluster.lower, Decimal("110"))
        self.assertEqual(cluster.upper, Decimal("111"))
        self.assertEqual(cluster.normalized_span, Decimal("0.01"))

    def test_four_wide_observations_fail(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "111", "112", "113"), 1)]
        self.assertIsNone(select_cluster(rows, "event-4", Decimal("100")))

    def test_non_consecutive_cluster_and_outlier_qualify(self) -> None:
        prices = ("110", "140", "110.2", "132", "110.5", "110.8")
        rows = [observation(i, price) for i, price in enumerate(prices, 1)]
        cluster = select_cluster(rows, "event-6", Decimal("100"))
        self.assertEqual([row.observation_price for row in cluster.members], [
            Decimal("110"), Decimal("110.2"), Decimal("110.5"), Decimal("110.8")
        ])

    def test_newest_observation_must_participate(self) -> None:
        prices = ("110", "110.2", "110.4", "110.6", "130")
        rows = [observation(i, price) for i, price in enumerate(prices, 1)]
        self.assertIsNone(select_cluster(rows, "event-5", Decimal("100")))

    def test_tightest_seed_is_selected_before_expansion(self) -> None:
        prices = ("110", "110.9", "111", "120", "120.1", "120.2", "120.3")
        rows = [observation(i, price) for i, price in enumerate(prices, 1)]
        cluster = select_cluster(rows, "event-7", Decimal("100"))
        self.assertEqual(cluster.lower, Decimal("120"))
        self.assertEqual(cluster.upper, Decimal("120.3"))

    def test_cluster_expands_to_adjacent_observations_within_full_span(self) -> None:
        prices = ("110", "110.2", "110.4", "110.6", "110.8", "112")
        rows = [observation(i, price) for i, price in enumerate(prices, 1)]
        cluster = select_cluster(rows, "event-4", Decimal("100"))
        self.assertEqual(cluster.observation_count, 5)
        self.assertEqual(cluster.lower, Decimal("110"))
        self.assertEqual(cluster.upper, Decimal("110.8"))

    def test_normalization_uses_full_ipda_width(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("1000", "1000.3", "1000.6", "1001"), 1)]
        self.assertIsNotNone(select_cluster(rows, "event-4", Decimal("100")))
        self.assertIsNone(select_cluster(rows, "event-4", Decimal("10")))

    def test_latest_window_ages_observation_one_out_on_event_twenty_one(self) -> None:
        rows = [observation(i, str(100 + i)) for i in range(1, 22)]
        window = latest_route_window(rows)
        self.assertEqual(len(window), 20)
        self.assertEqual(window[0].event_id, "event-2")
        self.assertEqual(window[-1].event_id, "event-21")
