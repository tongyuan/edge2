from __future__ import annotations

import unittest
from decimal import Decimal

from app.concentration import (
    ConcentrationResult,
    evaluate_concentration,
    latest_route_window,
    select_cluster,
)
from app.domain import PriceLocation, Route
from tests.helpers import observation


class ConcentrationTests(unittest.TestCase):
    def test_diagnostic_reports_insufficient_observations_without_a_candidate(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "120", "130"), 1)]
        diagnostic = evaluate_concentration(rows, Route.BTD).diagnostic

        self.assertEqual(diagnostic.result, ConcentrationResult.INSUFFICIENT_OBSERVATIONS)
        self.assertEqual(diagnostic.retained_observation_count, 3)
        self.assertEqual(diagnostic.minimum_required_count, 4)
        self.assertEqual(diagnostic.tested_window_count, 0)
        self.assertEqual(diagnostic.selected_observation_ids, ())
        self.assertIsNone(diagnostic.selected_lower)
        self.assertIsNone(diagnostic.observed_span)

    def test_exactly_four_tight_observations_qualify(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.3", "110.7", "111"), 1)]
        cluster = select_cluster(rows, "event-4", Decimal("100"))
        self.assertIsNotNone(cluster)
        self.assertEqual(cluster.lower, Decimal("110"))
        self.assertEqual(cluster.upper, Decimal("111"))
        self.assertEqual(cluster.normalized_span, Decimal("0.01"))
        diagnostic = evaluate_concentration(rows, Route.BTD).diagnostic
        self.assertEqual(diagnostic.result, ConcentrationResult.QUALIFIES)
        self.assertEqual(diagnostic.observed_span, Decimal("1"))
        self.assertEqual(diagnostic.allowance, Decimal("1.00"))
        self.assertEqual(diagnostic.normalized_span, Decimal("0.01"))
        self.assertTrue(diagnostic.newest_observation_included)

    def test_four_wide_observations_fail(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "111", "112", "113"), 1)]
        self.assertIsNone(select_cluster(rows, "event-4", Decimal("100")))
        diagnostic = evaluate_concentration(rows, Route.BTD).diagnostic
        self.assertEqual(diagnostic.result, ConcentrationResult.TOO_DISPERSED)
        self.assertEqual(diagnostic.selected_observation_count, 4)
        self.assertEqual(diagnostic.observed_span, Decimal("3"))
        self.assertEqual(diagnostic.allowance, Decimal("1.00"))
        self.assertEqual(diagnostic.proposed_midpoint, Decimal("111.5"))
        self.assertEqual(diagnostic.proposed_structural_location, PriceLocation.DEEP_DISCOUNT)
        self.assertTrue(diagnostic.structural_eligibility_passed)

    def test_first_outlier_is_excluded_when_recent_four_are_tight(self) -> None:
        prices = ("2326.95", "2400", "2403", "2406", "2409")
        rows = [
            observation(i, price, route=Route.STR, ipda_low="1500", ipda_high="2500")
            for i, price in enumerate(prices, 1)
        ]
        diagnostic = evaluate_concentration(rows, Route.STR).diagnostic

        self.assertEqual(diagnostic.result, ConcentrationResult.QUALIFIES)
        self.assertEqual(diagnostic.selected_observation_ids, ("event-2", "event-3", "event-4", "event-5"))
        self.assertEqual(diagnostic.selected_lower, Decimal("2400"))
        self.assertEqual(diagnostic.selected_upper, Decimal("2409"))
        self.assertEqual(diagnostic.observed_span, Decimal("9"))

    def test_first_outlier_is_excluded_but_recent_four_can_remain_dispersed(self) -> None:
        prices = ("2326.95", "2400", "2420", "2440", "2460")
        rows = [
            observation(i, price, route=Route.STR, ipda_low="1500", ipda_high="2500")
            for i, price in enumerate(prices, 1)
        ]
        diagnostic = evaluate_concentration(rows, Route.STR).diagnostic

        self.assertEqual(diagnostic.result, ConcentrationResult.TOO_DISPERSED)
        self.assertEqual(diagnostic.selected_observation_ids, ("event-2", "event-3", "event-4", "event-5"))
        self.assertEqual(diagnostic.observed_span, Decimal("60"))

    def test_tighter_historical_seed_excluding_newest_is_not_selected(self) -> None:
        prices = ("2400", "2401", "2402", "2403", "2500")
        rows = [
            observation(i, price, route=Route.STR, ipda_low="1000", ipda_high="3000")
            for i, price in enumerate(prices, 1)
        ]
        diagnostic = evaluate_concentration(rows, Route.STR).diagnostic

        self.assertEqual(diagnostic.result, ConcentrationResult.TOO_DISPERSED)
        self.assertNotIn("event-1", diagnostic.selected_observation_ids)
        self.assertIn("event-5", diagnostic.selected_observation_ids)
        self.assertTrue(diagnostic.newest_observation_included)

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

        full_width_rows = [
            observation(i, price, ipda_low="900", ipda_high="1000")
            for i, price in enumerate(("999", "999.3", "999.6", "1000"), 1)
        ]
        narrow_rows = [*full_width_rows[:-1], observation(4, "1000", ipda_low="990", ipda_high="1000")]
        self.assertTrue(evaluate_concentration(full_width_rows, Route.BTD).diagnostic.concentration_passed)
        self.assertFalse(evaluate_concentration(narrow_rows, Route.BTD).diagnostic.concentration_passed)

    def test_str_structural_eligibility_uses_production_location_check(self) -> None:
        premium_rows = [
            observation(i, price, route=Route.STR)
            for i, price in enumerate(("180", "180.2", "180.4", "180.6"), 1)
        ]
        discount_rows = [
            observation(i, price, route=Route.STR)
            for i, price in enumerate(("120", "120.2", "120.4", "120.6"), 1)
        ]
        premium = evaluate_concentration(premium_rows, Route.STR).diagnostic
        discount = evaluate_concentration(discount_rows, Route.STR).diagnostic

        self.assertEqual(premium.result, ConcentrationResult.QUALIFIES)
        self.assertTrue(premium.structural_eligibility_passed)
        self.assertEqual(premium.proposed_structural_location, PriceLocation.DEEP_PREMIUM)
        self.assertEqual(discount.result, ConcentrationResult.STRUCTURALLY_INELIGIBLE)
        self.assertFalse(discount.structural_eligibility_passed)
        self.assertEqual(discount.proposed_structural_location, PriceLocation.DEEP_DISCOUNT)

    def test_seed_tie_breaking_is_deterministic(self) -> None:
        rows = [
            observation(1, "109"),
            observation(2, "110"),
            observation(3, "111"),
            observation(4, "112"),
            observation(5, "110.5"),
        ]
        forward = evaluate_concentration(rows, Route.BTD).diagnostic
        reversed_input = evaluate_concentration(list(reversed(rows)), Route.BTD).diagnostic

        expected_ids = ("event-1", "event-2", "event-5", "event-3")
        self.assertEqual(forward.selected_observation_ids, expected_ids)
        self.assertEqual(reversed_input.selected_observation_ids, expected_ids)
        self.assertEqual(forward.tested_window_count, 2)

    def test_latest_window_ages_observation_one_out_on_event_twenty_one(self) -> None:
        rows = [observation(i, str(100 + i)) for i in range(1, 22)]
        window = latest_route_window(rows)
        self.assertEqual(len(window), 20)
        self.assertEqual(window[0].event_id, "event-2")
        self.assertEqual(window[-1].event_id, "event-21")
