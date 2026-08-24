from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.activation_feasibility import (
    ALGORITHM_A,
    ALGORITHM_B,
    ActivationFeasibilityService,
    Scenario,
    evaluate_feasibility_concentration,
)
from app.concentration import ConcentrationResult, evaluate_concentration
from app.db import connect
from app.domain import Route
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.helpers import BASE_TIME, observation


FIXED_NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def report_for(rows):
    return ActivationFeasibilityService(
        lambda: tuple(rows),
        clock=lambda: FIXED_NOW,
    ).generate_report()


def scenario(report, algorithm: str, minimum: int, allowance: int):
    return next(
        item
        for item in report["scenarios"]
        if item["algorithm"] == algorithm
        and item["minimum_observations"] == minimum
        and item["allowance_percent"] == allowance
    )


def detail(report, symbol: str, route: str, algorithm: str, minimum: int, allowance: int):
    return next(
        item
        for item in report["sequence_details"]
        if item["symbol"] == symbol
        and item["route"] == route
        and item["algorithm"] == algorithm
        and item["minimum_observations"] == minimum
        and item["allowance_percent"] == allowance
    )


class ActivationFeasibilityTests(unittest.TestCase):
    def test_algorithm_a_four_at_one_percent_is_exact_production_parity(self) -> None:
        rows = [
            observation(index, price)
            for index, price in enumerate(
                ("109", "110", "110.2", "110.4", "110.6", "110.8"),
                1,
            )
        ]
        production = evaluate_concentration(rows, Route.BTD)
        feasibility = evaluate_feasibility_concentration(
            rows,
            Route.BTD,
            Scenario(ALGORITHM_A, 4, Decimal("0.01")),
        )

        self.assertEqual(feasibility, production)
        self.assertEqual(feasibility.diagnostic.selected_observation_ids, production.diagnostic.selected_observation_ids)
        self.assertEqual(feasibility.cluster.members, production.cluster.members)
        self.assertEqual(feasibility.cluster.lower, production.cluster.lower)
        self.assertEqual(feasibility.cluster.upper, production.cluster.upper)
        self.assertEqual(feasibility.cluster.midpoint, production.cluster.midpoint)
        self.assertEqual(feasibility.cluster.normalized_span, production.cluster.normalized_span)
        self.assertEqual(feasibility.diagnostic.proposed_structural_location, production.diagnostic.proposed_structural_location)

    def test_parameter_grid_and_empty_report_are_complete(self) -> None:
        report = report_for([])

        self.assertEqual(len(report["scenarios"]), 30)
        self.assertEqual(len(report["comparisons"]), 15)
        self.assertEqual(len([item for item in report["scenarios"] if item["algorithm"] == "A"]), 15)
        self.assertEqual(len([item for item in report["scenarios"] if item["algorithm"] == "B"]), 15)
        self.assertEqual({item["minimum_observations"] for item in report["scenarios"]}, {2, 3, 4})
        self.assertEqual({item["allowance_percent"] for item in report["scenarios"]}, {1, 2, 3, 4, 5})
        self.assertEqual(report["sequence_details"], [])
        self.assertEqual(report["total_observations_evaluated"], 0)
        self.assertIsNone(report["earliest_observation_at"])
        self.assertTrue(all(item["small_sample"] for item in report["scenarios"]))

    def test_algorithm_a_searches_price_space_b_uses_latest_consecutive_seed(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "150", "110.2", "110.4"), 1)]
        report = report_for(rows)
        a = detail(report, "SPXUSDT", "BTD", "A", 3, 1)
        b = detail(report, "SPXUSDT", "BTD", "B", 3, 1)

        self.assertTrue(a["activated"])
        self.assertEqual(a["ordinal_route_observation_number"], 4)
        self.assertFalse(b["activated"])
        self.assertEqual(b["classification"], "DISPERSED")
        self.assertEqual(b["closest_evaluation"]["ordinal_route_observation_number"], 4)

    def test_latest_twenty_newest_participation_and_route_isolation(self) -> None:
        btd_rows = [observation(1, "110")]
        btd_rows.extend(observation(i, str(150 + i)) for i in range(2, 21))
        btd_rows.append(observation(21, "110.1"))
        str_rows = [
            observation(100 + i, price, route=Route.STR)
            for i, price in enumerate(("180", "180.2"), 1)
        ]

        aged = evaluate_feasibility_concentration(
            btd_rows,
            Route.BTD,
            Scenario(ALGORITHM_A, 2, Decimal("0.01")),
        )
        isolated = evaluate_feasibility_concentration(
            [*btd_rows[-1:], *str_rows],
            Route.STR,
            Scenario(ALGORITHM_A, 2, Decimal("0.01")),
        )

        self.assertEqual(aged.diagnostic.retained_observation_count, 20)
        self.assertNotIn("event-1", aged.diagnostic.selected_observation_ids)
        self.assertTrue(aged.diagnostic.newest_observation_included)
        self.assertEqual(isolated.result, ConcentrationResult.QUALIFIES)
        self.assertTrue(all(member.route is Route.STR for member in isolated.cluster.members))

    def test_replay_is_chronological_with_deterministic_equal_timestamp_order(self) -> None:
        rows = [
            observation(3, "110.2", observed_offset=10, received_offset=30),
            observation(1, "110", observed_offset=10, received_offset=10),
            observation(2, "110.1", observed_offset=10, received_offset=20),
        ]
        forward = report_for(rows)
        reverse = report_for(list(reversed(rows)))

        self.assertEqual(forward, reverse)
        selected = detail(forward, "SPXUSDT", "BTD", "B", 2, 1)
        self.assertEqual(selected["ordinal_route_observation_number"], 2)
        self.assertEqual(selected["formation_duration_seconds"], "0")

    def test_first_qualification_only_and_seed_based_duration(self) -> None:
        rows = [
            observation(1, "110", observed_offset=0),
            observation(2, "110.1", observed_offset=10),
            observation(3, "110.2", observed_offset=20),
            observation(4, "110.3", observed_offset=30),
        ]
        report = report_for(rows)
        summary = scenario(report, "A", 2, 1)
        selected = detail(report, "SPXUSDT", "BTD", "A", 2, 1)

        self.assertEqual(summary["eligible_symbol_route_sequences"], 1)
        self.assertEqual(summary["hypothetical_activations"], 1)
        self.assertEqual(selected["ordinal_route_observation_number"], 2)
        self.assertEqual(
            selected["current_evaluation"]["ordinal_route_observation_number"],
            4,
        )

        expanded_rows = [
            observation(1, "110", observed_offset=0),
            observation(2, "110.1", observed_offset=10, ipda_low="100", ipda_high="120"),
            observation(3, "110.2", observed_offset=20),
        ]
        expanded = detail(report_for(expanded_rows), "SPXUSDT", "BTD", "A", 2, 1)
        self.assertEqual(expanded["seed_observation_count"], 2)
        self.assertEqual(expanded["expanded_observation_count"], 3)
        self.assertEqual(expanded["formation_duration_seconds"], "10")

    def test_denominators_are_sequence_totals_and_differ_by_minimum(self) -> None:
        rows = [
            observation(1, "110", symbol="AAA"), observation(2, "110.2", symbol="AAA"),
            observation(11, "111", symbol="BBB"), observation(12, "111.2", symbol="BBB"), observation(13, "111.4", symbol="BBB"),
            observation(21, "180", symbol="CCC", route=Route.STR), observation(22, "180.2", symbol="CCC", route=Route.STR), observation(23, "180.4", symbol="CCC", route=Route.STR), observation(24, "180.6", symbol="CCC", route=Route.STR),
            observation(31, "110", symbol="DDD"), observation(32, "120", symbol="DDD"), observation(33, "130", symbol="DDD"), observation(34, "140", symbol="DDD"),
        ]
        report = report_for(rows)

        self.assertEqual(scenario(report, "A", 2, 1)["eligible_symbol_route_sequences"], 4)
        self.assertEqual(scenario(report, "A", 3, 1)["eligible_symbol_route_sequences"], 3)
        self.assertEqual(scenario(report, "A", 4, 1)["eligible_symbol_route_sequences"], 2)
        self.assertEqual(scenario(report, "A", 2, 1)["activation_frequency"], {
            "numerator": 3, "denominator": 4, "percentage": "75.0"
        })
        self.assertEqual(scenario(report, "A", 4, 1)["insufficient_sequences"], 2)

    def test_event_time_full_ipda_width_decimal_and_structural_eligibility(self) -> None:
        rows = [
            observation(1, "110", ipda_low="100", ipda_high="200"),
            observation(2, "111.5", ipda_low="100", ipda_high="300"),
        ]
        evaluation = evaluate_feasibility_concentration(
            rows,
            Route.BTD,
            Scenario(ALGORITHM_A, 2, Decimal("0.01")),
        )
        self.assertEqual(evaluation.result, ConcentrationResult.QUALIFIES)
        self.assertEqual(evaluation.diagnostic.allowance, Decimal("2.00"))
        self.assertEqual(evaluation.cluster.normalized_span, Decimal("0.0075"))

        wrong_route = [
            observation(i, price, route=Route.BTD)
            for i, price in enumerate(("180", "180.2"), 1)
        ]
        self.assertEqual(
            evaluate_feasibility_concentration(
                wrong_route,
                Route.BTD,
                Scenario(ALGORITHM_A, 2, Decimal("0.01")),
            ).result,
            ConcentrationResult.STRUCTURALLY_INELIGIBLE,
        )

    def test_qualification_ratio_near_miss_and_insufficient_are_distinct(self) -> None:
        rows = [observation(1, "110"), observation(2, "111.5")]
        report = report_for(rows)
        near = detail(report, "SPXUSDT", "BTD", "A", 2, 1)
        insufficient = detail(report, "SPXUSDT", "BTD", "A", 3, 1)

        self.assertEqual(near["classification"], "NEAR_MISS")
        self.assertEqual(near["closest_qualification_ratio"], "1.5")
        self.assertEqual(near["closest_minimum_required_allowance_pct"], "1.500")
        self.assertEqual(
            near["closest_evaluation"]["minimum_required_allowance_pct"],
            "1.500",
        )
        self.assertEqual(insufficient["classification"], "INSUFFICIENT")
        self.assertIsNone(insufficient["closest_qualification_ratio"])
        self.assertIsNone(insufficient["closest_minimum_required_allowance_pct"])

    def test_first_activation_and_summary_expose_exact_required_percentage(self) -> None:
        rows = [observation(1, "110"), observation(2, "110.123456")]
        report = report_for(rows)
        activated = detail(report, "SPXUSDT", "BTD", "A", 2, 1)
        summary = scenario(report, "A", 2, 1)

        self.assertTrue(activated["activated"])
        self.assertEqual(
            activated["minimum_required_allowance_pct"],
            "0.12345600",
        )
        self.assertEqual(
            summary["median_minimum_required_allowance_pct_at_qualification"],
            "0.12345600",
        )
        self.assertEqual(activated["normalized_span"], "0.00123456")

    def test_report_percentages_and_diagnosis_are_derived_from_report_values(self) -> None:
        rows = [
            observation(i, price, symbol="WLDUSDT")
            for i, price in enumerate(("110", "110.3", "110.7", "111.13"), 1)
        ]
        report = report_for(rows)
        production = scenario(report, "A", 4, 1)
        production_detail = detail(report, "WLDUSDT", "BTD", "A", 4, 1)
        diagnosis = report["diagnosis"]

        self.assertEqual(len(report["scenarios"]), 30)
        self.assertEqual(len(report["comparisons"]), 15)
        self.assertEqual(production["hypothetical_activations"], 0)
        self.assertEqual(
            production_detail["closest_minimum_required_allowance_pct"],
            "1.1300",
        )
        self.assertEqual(diagnosis["sample_assessment"]["code"], "SAMPLE_PRELIMINARY")
        self.assertEqual(diagnosis["sample_assessment"]["numerator"], 1)
        self.assertIn(
            "Algorithm A with four observations and 1% activated 0 of 1",
            diagnosis["production_feasibility"]["text"],
        )
        self.assertEqual(
            [item["scenario_id"] for item in diagnosis["count_sensitivity"]["settings"]],
            ["A-2-1", "A-3-1", "A-4-1"],
        )
        allowance = diagnosis["allowance_sensitivity"]
        self.assertEqual(allowance["first_activating_allowance_pct"], 2)
        self.assertEqual(
            [(item["from_allowance_pct"], item["to_allowance_pct"]) for item in allowance["increases"]],
            [(1, 2)],
        )
        self.assertIn(
            {"from_allowance_pct": 2, "to_allowance_pct": 5, "activation_count": 1,
             "scenario_ids": ["A-4-2", "A-4-3", "A-4-4", "A-4-5"]},
            allowance["plateaus"],
        )
        near_miss = diagnosis["closest_production_near_misses"][0]
        self.assertEqual(near_miss["symbol"], "WLDUSDT")
        self.assertEqual(near_miss["minimum_required_allowance_pct"], "1.1300")
        self.assertEqual(near_miss["shortfall_percentage_points"], "0.1300")
        self.assertEqual(near_miss["candidate_lower_boundary"], "110")
        self.assertEqual(near_miss["candidate_upper_boundary"], "111.13")
        self.assertEqual(near_miss["candidate_observation_count"], 4)
        self.assertTrue(near_miss["candidate_timestamp"].endswith("Z"))

        comparison = diagnosis["algorithm_comparison"]
        expected_equal = sum(
            item["algorithm_a_activations"] == item["algorithm_b_activations"]
            for item in report["comparisons"]
        )
        self.assertEqual(comparison["equal_activation_counts"], expected_equal)
        self.assertEqual(
            comparison["equal_activation_counts"]
            + comparison["algorithm_a_more"]
            + comparison["algorithm_b_more"],
            15,
        )

    def test_current_near_miss_matches_latest_monitor_window_not_historical_best(self) -> None:
        rows = [
            observation(i, price, symbol="WLDUSDT")
            for i, price in enumerate(
                ("110", "110.3", "110.7", "111.13", "111.89"),
                1,
            )
        ]
        report = report_for(rows)
        production_detail = detail(report, "WLDUSDT", "BTD", "A", 4, 1)

        self.assertFalse(production_detail["activated"])
        self.assertEqual(
            production_detail["closest_evaluation"][
                "minimum_required_allowance_pct"
            ],
            "1.1300",
        )
        self.assertEqual(
            production_detail["current_evaluation"][
                "minimum_required_allowance_pct"
            ],
            "1.5900",
        )
        self.assertEqual(
            report["diagnosis"]["current_production_near_misses"][0][
                "minimum_required_allowance_pct"
            ],
            "1.5900",
        )
        self.assertEqual(
            report["diagnosis"]["closest_production_near_misses"][0][
                "minimum_required_allowance_pct"
            ],
            "1.1300",
        )

    def test_diagnosis_handles_activation_empty_sample_and_structural_exclusion(self) -> None:
        active_report = report_for([
            observation(i, price)
            for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        ])
        self.assertEqual(
            active_report["diagnosis"]["production_feasibility"]["code"],
            "PRODUCTION_ACTIVATION_OBSERVED",
        )
        self.assertIn(
            "activated 1 of 1 sequences (100.0%)",
            active_report["diagnosis"]["production_feasibility"]["text"],
        )

        empty = report_for([])
        self.assertEqual(
            empty["diagnosis"]["production_feasibility"]["code"],
            "PRODUCTION_INSUFFICIENT_OBSERVATIONS",
        )
        self.assertIsNone(
            empty["diagnosis"]["allowance_sensitivity"]["first_activating_allowance_pct"]
        )
        self.assertEqual(empty["diagnosis"]["closest_production_near_misses"], [])
        self.assertEqual(empty["diagnosis"]["current_production_near_misses"], [])

        structurally_ineligible = report_for([
            observation(i, price, symbol="PREMIUM")
            for i, price in enumerate(("180", "180.4", "180.8", "181.2"), 1)
        ])
        candidate = detail(structurally_ineligible, "PREMIUM", "BTD", "A", 4, 1)
        self.assertEqual(candidate["closest_minimum_required_allowance_pct"], "1.200")
        self.assertFalse(
            candidate["closest_evaluation"]["structural_eligibility_passed"]
        )
        self.assertEqual(
            structurally_ineligible["diagnosis"]["closest_production_near_misses"],
            [],
        )
        self.assertEqual(
            structurally_ineligible["diagnosis"]["current_production_near_misses"],
            [],
        )

    def test_diagnosis_contains_no_automatic_policy_or_trading_claim(self) -> None:
        report = report_for([
            observation(i, price)
            for i, price in enumerate(("110", "110.3", "110.7", "111.13"), 1)
        ])
        diagnosis_text = json.dumps(report["diagnosis"], sort_keys=True).lower()
        for prohibited in (
            "change production to",
            "use algorithm b",
            "this mrz is reliable",
            "this scenario is optimal",
            "trading recommendation",
        ):
            self.assertNotIn(prohibited, diagnosis_text)

    def test_production_near_misses_sort_by_exact_required_allowance(self) -> None:
        rows = []
        for offset, symbol, upper in (
            (0, "ZZZ", "111.90"),
            (10, "WLDUSDT", "111.13"),
            (20, "AAA", "111.05"),
        ):
            rows.extend(
                observation(offset + index, price, symbol=symbol)
                for index, price in enumerate(("110", "110.3", "110.7", upper), 1)
            )
        near_misses = report_for(rows)["diagnosis"]["closest_production_near_misses"]

        self.assertEqual(
            [item["symbol"] for item in near_misses],
            ["AAA", "WLDUSDT", "ZZZ"],
        )
        self.assertEqual(
            [item["minimum_required_allowance_pct"] for item in near_misses],
            ["1.0500", "1.1300", "1.900"],
        )

    def test_ab_categories_are_exhaustive_and_b_only_is_not_assumed_impossible(self) -> None:
        a_only = [observation(i, price, symbol="AONLY") for i, price in enumerate(("110", "150", "110.2", "110.4"), 1)]
        b_only = [
            observation(11, "150.2", symbol="BONLY", ipda_low="145", ipda_high="155"),
            observation(12, "150.1", symbol="BONLY", ipda_low="145", ipda_high="155"),
            observation(13, "148", symbol="BONLY", ipda_low="145", ipda_high="155"),
            observation(14, "148.2", symbol="BONLY", ipda_low="145", ipda_high="155"),
            observation(15, "149.9", symbol="BONLY", ipda_low="100", ipda_high="198.2"),
        ]
        report = report_for([*a_only, *b_only])
        comparison = next(
            item for item in report["comparisons"]
            if item["minimum_observations"] == 3 and item["allowance_percent"] == 2
        )

        total = (
            comparison["both_activated"] + comparison["algorithm_a_only"]
            + comparison["algorithm_b_only"] + comparison["neither_activated"]
        )
        self.assertEqual(total, comparison["eligible_symbol_route_sequences"])
        self.assertGreaterEqual(comparison["algorithm_a_only"], 1)
        self.assertGreaterEqual(comparison["algorithm_b_only"], 1)
        self.assertEqual(
            {item["category"] for item in comparison["disagreements"]},
            {"A_ONLY", "B_ONLY"},
        )

    def test_report_is_deterministic_and_never_exposes_event_ids(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        first = report_for(rows)
        second = report_for(list(reversed(rows)))

        self.assertEqual(first, second)
        serialized = json.dumps(first, sort_keys=True)
        self.assertNotIn("event-", serialized)
        self.assertEqual(first["current_production_rule"]["scenario_id"], "A-4-1")


class ActivationFeasibilityDatabaseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def snapshot(self):
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                result = {}
                for table, order in (
                    ("observations", "id"),
                    ("active_mrz", "symbol"),
                    ("mrz_events", "id"),
                    ("ingestion_metrics", "singleton"),
                ):
                    cursor.execute(
                        f"SELECT row_to_json(snapshot_row)::text FROM "
                        f"(SELECT * FROM {table} ORDER BY {order}) snapshot_row"
                    )
                    result[table] = tuple(row[0] for row in cursor.fetchall())
                return result
        finally:
            connection.close()

    def test_generating_report_does_not_mutate_operational_state(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            payload = ObservationPayload.model_validate({
                "schema_version": "4.3",
                "event_id": f"feasibility-db-{index}",
                "symbol": "SPXUSDT",
                "route": "BTD",
                "observation_type": "reclaim",
                "observation_price": price,
                "ipda_20w_high": "200",
                "ipda_20w_low": "100",
                "observed_at": BASE_TIME.replace(second=index),
            })
            self.repository.ingest(payload, Decimal("0.01"))

        before = self.snapshot()
        report = ActivationFeasibilityService(
            self.repository.schema_43_observations,
            clock=lambda: FIXED_NOW,
        ).generate_report()
        after = self.snapshot()

        self.assertEqual(before, after)
        self.assertEqual(report["total_observations_evaluated"], 4)
        self.assertEqual(report["current_production_rule"]["result"]["hypothetical_activations"], 1)
