from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.concentration import (
    CONCENTRATION_SPAN_THRESHOLD,
    MIN_CLUSTER_OBSERVATIONS,
    ConcentrationResult,
    evaluate_concentration,
)
from app.domain import Route
from app.near_miss_diagnosis import (
    CONCENTRATION_TREND_EPSILON_PP,
    NEAR_MISS_DIAGNOSIS_LOOKBACK_EPISODES,
    build_near_miss_diagnosis,
    classify_concentration_trend,
    ranges_overlap,
)
from tests.helpers import observation


BASE_TIME = datetime(2026, 9, 1, tzinfo=timezone.utc)


def candidate(
    allowance: str = "1.05",
    *,
    lower: str = "100",
    upper: str = "110",
    route: str = "BTD",
) -> dict[str, object]:
    return {
        "symbol": "KOSPI",
        "route": route,
        "candidate_identity": "f" * 64,
        "candidate_lower_boundary": lower,
        "candidate_upper_boundary": upper,
        "candidate_midpoint": str((Decimal(lower) + Decimal(upper)) / 2),
        "minimum_required_allowance_pct": allowance,
        "candidate_observation_count": 4,
        "candidate_timestamp": "2026-09-11T12:00:00Z",
        "structural_location": "deep_discount_core_mrz",
    }


def episode(
    number: int,
    allowance: str,
    *,
    lower: str = "99",
    upper: str = "105",
    route: str = "BTD",
    reliable: bool = True,
    ended: bool = True,
) -> dict[str, object]:
    midpoint = (Decimal(lower) + Decimal(upper)) / 2
    started_at = BASE_TIME + timedelta(days=number)
    return {
        "id": number,
        "episode_key": f"episode-{number}",
        "symbol": "KOSPI",
        "route_owner": route,
        "started_at": started_at,
        "ended_at": started_at + timedelta(hours=1) if ended else None,
        "ended_reason": "NO_LONGER_CURRENT" if ended else None,
        "canonical_candidate_identity": f"{number:064x}",
        "canonical_candidate_event_id": f"event-{number}",
        "canonical_candidate_lower": Decimal(lower),
        "canonical_candidate_upper": Decimal(upper),
        "canonical_candidate_midpoint": midpoint,
        "canonical_structural_location": "deep_discount_core_mrz",
        "canonical_minimum_required_allowance_pct": Decimal(allowance),
        "canonical_shortfall_percentage_points": Decimal(allowance) - Decimal("1"),
        "canonical_supporting_observation_count": 4,
        "canonical_supporting_observation_ids": [f"event-{number}-{i}" for i in range(4)],
        "canonical_candidate_timestamp": started_at,
        "canonical_snapshot_reliable": reliable,
        "canonical_updated_at": started_at,
    }


class NearMissDiagnosisTests(unittest.TestCase):
    def diagnose(
        self,
        allowances: list[str],
        *,
        ranges: list[tuple[str, str]] | None = None,
    ) -> dict[str, object]:
        current_allowance = allowances[-1]
        prior_allowances = allowances[:-1]
        ranges = ranges or [("99", "105")] * len(allowances)
        rows = [
            episode(index, allowance, lower=ranges[index - 1][0], upper=ranges[index - 1][1])
            for index, allowance in enumerate(prior_allowances, 1)
        ]
        rows.append(episode(99, current_allowance, ended=False))
        return build_near_miss_diagnosis(
            candidate(
                current_allowance,
                lower=ranges[-1][0],
                upper=ranges[-1][1],
            ),
            rows,
        )

    def test_one_episode_has_no_diagnosis(self) -> None:
        result = self.diagnose(["1.05"])
        self.assertFalse(result["available"])
        self.assertIsNone(result["diagnosis"])
        self.assertIsNone(result["concentration_trend"])
        self.assertEqual(result["episode_count"], 1)

    def test_two_episode_state_machine(self) -> None:
        cases = (
            (["1.40", "1.20"], "TIGHTENING", "CONVERGING"),
            (["1.08", "1.07"], "STABLE", "PERSISTENT"),
            (["1.08", "1.20"], "WIDENING", "DISPERSING"),
        )
        for allowances, trend, diagnosis in cases:
            with self.subTest(allowances=allowances):
                result = self.diagnose(allowances)
                self.assertEqual(result["concentration_trend"], trend)
                self.assertEqual(result["diagnosis"], diagnosis)

    def test_multi_episode_trends(self) -> None:
        cases = (
            (["1.40", "1.20", "1.05"], "TIGHTENING", "CONVERGING"),
            (["1.08", "1.09", "1.08"], "STABLE", "PERSISTENT"),
            (["1.08", "1.20", "1.40"], "WIDENING", "DISPERSING"),
            (["1.40", "1.10", "1.30"], "MIXED", "INCONSISTENT"),
        )
        for allowances, trend, diagnosis in cases:
            with self.subTest(allowances=allowances):
                result = self.diagnose(allowances)
                self.assertEqual(result["allowance_history"], allowances)
                self.assertEqual(result["concentration_trend"], trend)
                self.assertEqual(result["diagnosis"], diagnosis)

    def test_same_open_episode_is_not_false_recurrence(self) -> None:
        open_snapshot = episode(1, "1.35", ended=False)
        result = build_near_miss_diagnosis(candidate("1.25"), [open_snapshot])
        self.assertEqual(result["episode_count"], 1)
        self.assertEqual(result["allowance_history"], ["1.25"])
        self.assertFalse(result["available"])

    def test_route_isolation(self) -> None:
        rows = [
            episode(1, "1.40", route="STR"),
            episode(2, "1.30", route="BTD", ended=False),
        ]
        result = build_near_miss_diagnosis(candidate("1.20", route="BTD"), rows)
        self.assertEqual(result["episode_count"], 1)
        self.assertFalse(result["available"])

    def test_interval_overlap_is_inclusive(self) -> None:
        self.assertTrue(ranges_overlap(Decimal("100"), Decimal("110"), Decimal("105"), Decimal("115")))
        self.assertTrue(ranges_overlap(Decimal("100"), Decimal("110"), Decimal("110"), Decimal("120")))
        self.assertTrue(ranges_overlap(Decimal("100"), Decimal("110"), Decimal("101"), Decimal("109")))
        self.assertFalse(ranges_overlap(Decimal("100"), Decimal("110"), Decimal("110.01"), Decimal("120")))

    def test_non_overlapping_history_is_inconsistent(self) -> None:
        result = self.diagnose(
            ["1.40", "1.20"],
            ranges=[("80", "90"), ("100", "110")],
        )
        self.assertEqual(result["same_area_count"], 1)
        self.assertEqual(result["concentration_trend"], "TIGHTENING")
        self.assertEqual(result["diagnosis"], "INCONSISTENT")

    def test_recent_window_excludes_old_episodes_but_history_keeps_them(self) -> None:
        result = self.diagnose(["1.45", "1.40", "1.35", "1.30", "1.25", "1.20"])
        self.assertEqual(
            result["episode_count"],
            NEAR_MISS_DIAGNOSIS_LOOKBACK_EPISODES,
        )
        self.assertEqual(result["allowance_history"], ["1.40", "1.35", "1.30", "1.25", "1.20"])
        self.assertEqual(len(result["episodes"]), 6)
        self.assertFalse(result["episodes"][0]["included_in_diagnosis"])

    def test_unreliable_legacy_entry_snapshots_are_not_evidence(self) -> None:
        rows = [
            episode(1, "1.40", reliable=False),
            episode(2, "1.20", ended=False),
        ]
        result = build_near_miss_diagnosis(candidate("1.20"), rows)
        self.assertEqual(result["excluded_unreliable_episode_count"], 1)
        self.assertEqual(result["episode_count"], 1)
        self.assertFalse(result["available"])

    def test_epsilon_and_production_constants_are_isolated(self) -> None:
        self.assertEqual(CONCENTRATION_TREND_EPSILON_PP, Decimal("0.02"))
        self.assertEqual(
            classify_concentration_trend([Decimal("1.08"), Decimal("1.06")]),
            "STABLE",
        )
        self.assertEqual(CONCENTRATION_SPAN_THRESHOLD, Decimal("0.01"))
        self.assertEqual(MIN_CLUSTER_OBSERVATIONS, 4)

    def test_converging_1_05_candidate_remains_a_production_near_miss(self) -> None:
        result = self.diagnose(["1.40", "1.05"])
        self.assertEqual(result["diagnosis"], "CONVERGING")
        rows = [
            observation(index, price)
            for index, price in enumerate(
                ("110", "110.30", "110.70", "111.05"),
                1,
            )
        ]
        production = evaluate_concentration(rows, Route.BTD)
        self.assertEqual(
            production.diagnostic.minimum_required_allowance_pct,
            Decimal("1.05"),
        )
        self.assertEqual(production.result, ConcentrationResult.TOO_DISPERSED)
        self.assertIsNone(production.cluster)


if __name__ == "__main__":
    unittest.main()
