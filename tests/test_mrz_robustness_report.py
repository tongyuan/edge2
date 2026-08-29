from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from app.domain import Route
from app.feasibility import route_interpretation as canonical_route_interpretation
from app.mrz_robustness import MRZRobustnessService
from app.mrz_robustness_report import MRZRobustnessReportService
from app.state_engine import replay_symbol
from tests.helpers import observation


FIXED_NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def history(
    symbol: str,
    prices: tuple[str, ...],
    *,
    start: int = 0,
    route: Route = Route.BTD,
):
    return tuple(
        observation(
            start + index,
            price,
            symbol=symbol,
            route=route,
            event_id=f"{symbol}-{index}",
            observed_offset=start + index,
            received_offset=start + index,
        )
        for index, price in enumerate(prices, 1)
    )


def report_for(*histories):
    observations = tuple(item for rows in histories for item in rows)
    return MRZRobustnessReportService(
        lambda: observations,
        clock=lambda: FIXED_NOW,
    ).generate_report()


def detail(report, history_id: str):
    return next(
        item for item in report["symbol_level_detail"]
        if item["history_id"] == history_id
    )


class MRZRobustnessReportTests(unittest.TestCase):
    def test_route_role_outcomes_reuse_canonical_btd_and_str_classifier(self) -> None:
        btd = history(
            "BTDROLE",
            ("110", "110.2", "110.4", "110.6", "110.5", "110.1", "110.3"),
        )
        str_rows = history(
            "STRROLE",
            ("170", "170.2", "170.4", "170.6", "170.1", "170.5", "170.3"),
            route=Route.STR,
            start=20,
        )
        with patch(
            "app.mrz_robustness_report.route_interpretation",
            wraps=canonical_route_interpretation,
        ) as classify:
            report = report_for(btd, str_rows)

        self.assertGreater(classify.call_count, 0)
        for history_id in ("BTDROLE:BTD", "STRROLE:STR"):
            response = detail(report, history_id)["policies"][0]["structural_response"]
            self.assertEqual(response["supportive_outcome_count"], 1)
            self.assertEqual(response["adverse_outcome_count"], 1)
            self.assertEqual(response["neutral_unresolved_outcome_count"], 1)
            self.assertEqual(response["resolved_outcome_count"], 2)
            self.assertEqual(response["supportive_rate"], {
                "numerator": 1,
                "denominator": 2,
                "percentage": "50.0",
            })
            self.assertEqual(response["adverse_rate"], {
                "numerator": 1,
                "denominator": 2,
                "percentage": "50.0",
            })
            self.assertEqual(response["supportive_to_adverse_balance"], "1 : 1")
            self.assertEqual(response["first_supportive"], {
                "observation_number": 1,
                "seconds_from_activation": "1",
            })
            self.assertEqual(response["first_adverse"], {
                "observation_number": 2,
                "seconds_from_activation": "2",
            })
            self.assertTrue(response["early_adverse"])
            self.assertEqual(response["classifier"], "TRADING_WINDOW_SIGNED_DISPLACEMENT")

        production = report["current_production_robustness"]
        self.assertEqual(production["supportive_outcome_count"], 2)
        self.assertEqual(production["adverse_outcome_count"], 2)
        self.assertEqual(production["resolved_case_count"], 2)
        self.assertEqual(production["unresolved_case_count"], 0)
        self.assertEqual(production["median_time_to_first_supportive_seconds"], "1")
        self.assertEqual(production["median_time_to_first_adverse_seconds"], "2")
        self.assertEqual(
            [(row["route"], row["supportive_outcome_count"], row["adverse_outcome_count"])
             for row in production["route_breakdown"]],
            [("BTD", 1, 1), ("STR", 1, 1)],
        )

    def test_neutral_and_missing_post_activation_evidence_remain_unresolved(self) -> None:
        neutral = history(
            "NEUTRAL",
            ("110", "110.2", "110.4", "110.6", "110.3"),
        )
        no_post = history("NOPOST", ("110", "110.2", "110.4", "110.6"), start=20)
        report = report_for(neutral, no_post)
        production = report["current_production_robustness"]

        self.assertEqual(production["formations_with_post_activation_evidence"], 1)
        self.assertEqual(production["resolved_case_count"], 0)
        self.assertEqual(production["unresolved_case_count"], 2)
        self.assertEqual(production["supportive_rate"]["denominator"], 0)
        self.assertIsNone(production["supportive_rate"]["percentage"])
        self.assertEqual(production["neutral_unresolved_outcome_count"], 1)
        self.assertEqual(production["early_adverse_incidence"]["denominator"], 1)
        self.assertEqual(report["sample_confidence"]["production_resolved_case_count"], 0)
        self.assertEqual(report["sample_confidence"]["production_unresolved_case_count"], 2)

    def test_geometry_metrics_are_retained_only_as_secondary_methodology(self) -> None:
        report = report_for(
            history("GEOMETRY", ("110", "110.2", "110.4", "110.6", "110.5"))
        )

        self.assertIn("median_containment_percentage", report["current_production_robustness"])
        self.assertIn("migration_pressure_incidence", report["current_production_robustness"])
        self.assertIn("wider frozen MRZs", report["methodology"]["geometry_note"])
        self.assertIn("secondary lifecycle diagnostics", report["methodology"]["geometry_note"])
        self.assertIn("canonical signed-displacement classifier", report["methodology"]["structural_response"])

    def test_policy_replay_uses_same_histories_fixed_count_and_own_activation(self) -> None:
        rows = history("TIMING", ("110", "110.4", "110.8", "111.4", "110.6"))
        report = report_for(rows)
        policies = report["policy_robustness_comparison"]
        symbol_policies = detail(report, "TIMING:BTD")["policies"]

        self.assertEqual(
            [item["eligible_symbol_route_histories"] for item in policies],
            [1, 1, 1],
        )
        self.assertEqual(
            [item["minimum_observations"] for item in policies],
            [4, 4, 4],
        )
        self.assertEqual(
            [item["formation_policy"]["allowance_percent"] for item in symbol_policies],
            ["1.00", "1.50", "2.00"],
        )
        self.assertEqual(symbol_policies[0]["activated_at"], "2026-08-20T12:00:05Z")
        self.assertEqual(symbol_policies[1]["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(symbol_policies[2]["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(
            (symbol_policies[0]["mrz"]["lower"], symbol_policies[0]["mrz"]["upper"]),
            ("110", "110.8"),
        )
        self.assertEqual(
            (symbol_policies[1]["mrz"]["lower"], symbol_policies[1]["mrz"]["upper"]),
            ("110", "111.4"),
        )

    def test_post_activation_measurement_is_strict_and_reuses_existing_services(self) -> None:
        rows = history(
            "MIG",
            ("110", "110.2", "110.4", "110.6", "120", "120.2", "120.4", "120.6"),
        )
        with patch(
            "app.feasibility.replay_symbol",
            wraps=replay_symbol,
        ) as replay, patch.object(
            MRZRobustnessService,
            "active_mrz_report",
            autospec=True,
            side_effect=MRZRobustnessService.active_mrz_report,
        ) as measure:
            report = report_for(rows)

        production = detail(report, "MIG:BTD")["policies"][0]
        self.assertGreaterEqual(replay.call_count, 3)
        self.assertGreater(measure.call_count, 0)
        self.assertTrue(all(call.kwargs["minimum_required_count"] == 4 for call in replay.call_args_list))
        self.assertEqual(
            [call.kwargs["concentration_threshold"] for call in replay.call_args_list[:3]],
            [Decimal("0.0100"), Decimal("0.0150"), Decimal("0.0200")],
        )
        self.assertEqual(production["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(production["post_activation_observation_count"], 4)
        self.assertEqual(production["containment"]["inside_observation_count"], 0)
        self.assertEqual(production["containment"]["total_observation_count"], 4)
        self.assertEqual(production["containment"]["percentage"], "0")
        self.assertTrue(production["lifecycle"]["completed"])
        self.assertFalse(production["lifecycle"]["censored"])
        self.assertEqual(production["observed_lifespan_seconds"], "4")
        self.assertEqual(production["lifecycle"]["time_to_migration_seconds"], "4")
        self.assertTrue(production["lifecycle"]["early_migration"])
        self.assertEqual(production["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(production["migration_pressure"]["time_to_first_pressure_seconds"], "1")
        self.assertEqual(production["successor_watch"]["status"], "SUCCESSOR_CANDIDATE")
        self.assertEqual(production["successor_watch"]["route"], "BTD")
        self.assertEqual(production["successor_watch"]["direction"], "UP")
        self.assertEqual(production["mechanical_lifecycle_status"], "MIGRATION_CANDIDATE")

    def test_lifespan_censoring_and_aggregates_expose_denominators(self) -> None:
        migrated = history(
            "MIG",
            ("110", "110.2", "110.4", "110.6", "120", "120.2", "120.4", "120.6"),
        )
        censored = history(
            "CENS",
            ("110", "110.2", "110.4", "110.6", "110.3"),
            start=20,
        )
        report = report_for(migrated, censored)
        production = report["current_production_robustness"]
        censored_policy = detail(report, "CENS:BTD")["policies"][0]

        self.assertFalse(censored_policy["lifecycle"]["completed"])
        self.assertTrue(censored_policy["lifecycle"]["censored"])
        self.assertEqual(censored_policy["observed_lifespan_seconds"], "1")
        self.assertIsNone(censored_policy["lifecycle"]["time_to_migration_seconds"])
        self.assertEqual(production["observed_lifespan_sample_count"], 2)
        self.assertEqual(production["completed_lifecycle_count"], 1)
        self.assertEqual(production["censored_lifecycle_count"], 1)
        self.assertEqual(production["time_to_migration_sample_count"], 1)
        self.assertEqual(production["migration_confirmation_incidence"]["denominator"], 2)
        self.assertEqual(production["route_integrity_maintained"], {
            "numerator": 2,
            "denominator": 2,
            "percentage": "100.0",
        })
        self.assertEqual(report["sample_confidence"]["production_formed_denominator"], 2)

    def test_incremental_cohorts_are_mutually_exclusive_and_deterministic(self) -> None:
        baseline = history("BASE", ("110", "110.2", "110.4", "110.6"))
        incremental_15 = history("INC15", ("110", "110.4", "110.8", "111.4"), start=20)
        incremental_20 = history("INC20", ("110", "110.6", "111.2", "111.8"), start=40)
        service = MRZRobustnessReportService(
            lambda: (*baseline, *incremental_15, *incremental_20),
            clock=lambda: FIXED_NOW,
        )

        first = service.generate_report()
        second = service.generate_report()
        cohorts = first["incremental_cohorts"]

        self.assertEqual(first, second)
        self.assertEqual(
            [cohort["code"] for cohort in cohorts],
            ["BASELINE_1_00", "INCREMENTAL_1_50", "INCREMENTAL_2_00"],
        )
        self.assertEqual([cohort["history_count"] for cohort in cohorts], [1, 1, 1])
        self.assertEqual(cohorts[0]["histories"], ["BASE:BTD"])
        self.assertEqual(cohorts[1]["histories"], ["INC15:BTD"])
        self.assertEqual(cohorts[2]["histories"], ["INC20:BTD"])
        self.assertEqual(
            [row["formed_mrz_count"] for row in first["policy_robustness_comparison"]],
            [1, 2, 3],
        )
        self.assertEqual(first["sample_confidence"]["production_mrz_formations"], 1)
        self.assertEqual(first["sample_confidence"]["production_formed_denominator"], 3)
        self.assertIsNone(first["evidence_interpretation"]["production_recommendation"])
        self.assertNotIn("recommended", str(first).lower())
        self.assertEqual(first["invariants"]["persistence"], "No replayed MRZ is persisted")

    def test_default_production_replay_is_identical_to_explicit_frozen_parameters(self) -> None:
        rows = history("PARITY", ("110", "110.2", "110.4", "110.6", "120"))

        self.assertEqual(
            replay_symbol(rows),
            replay_symbol(
                rows,
                minimum_required_count=4,
                concentration_threshold=Decimal("0.01"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
