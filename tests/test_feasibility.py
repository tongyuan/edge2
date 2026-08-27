from __future__ import annotations

import unittest
from dataclasses import replace
from decimal import Decimal

from app.domain import Route, StructuralLocation
from app.feasibility import (
    Cohort,
    aggregate_checkpoint,
    build_feasibility_report,
    checkpoint_measurement,
    cohort_report,
    containment,
    cross_cohort_diagnosis,
    diagnose_cohort,
    migration_interpretation,
    operator_outcome_language,
    primary_outcome_summary,
    reconstruct_episodes,
    route_interpretation,
    signed_displacement,
)
from app.state_engine import replay_symbol
from tests.helpers import observation


def btd_migration(symbol: str = "SPXUSDT"):
    prices = ("110", "110.2", "110.4", "110.6", "120", "120.2", "120.4", "120.6")
    return [observation(index, price, symbol=symbol) for index, price in enumerate(prices, 1)]


def str_migration(symbol: str = "BTCUSDT"):
    prices = ("180", "180.2", "180.4", "180.6", "170", "170.2", "170.4", "170.6")
    return [
        observation(index, price, symbol=symbol, route=Route.STR)
        for index, price in enumerate(prices, 1)
    ]


def source_rows(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)
    events = []
    active = []
    for symbol_rows in grouped.values():
        replay = replay_symbol(symbol_rows)
        events.extend(
            {
                "symbol": item.symbol,
                "sequence": item.sequence,
                "event_type": item.event_type.value,
                "trigger_event_id": item.trigger_event_id,
            }
            for item in replay.transitions
        )
        if replay.active_mrz:
            active.append(replay.active_mrz)
    return events, active


class EpisodeReconstructionTests(unittest.TestCase):
    def test_historical_activation_is_reconstructed_as_episode(self) -> None:
        result = reconstruct_episodes(btd_migration())
        first = result.episodes[0]
        self.assertEqual(first.activation_observation.event_id, "event-4")
        self.assertEqual(first.active_mrz.core_mrz_lower, Decimal("110"))
        self.assertEqual(first.outcome, "MIGRATED_UPWARD")

    def test_migration_terminates_previous_and_creates_new_episode(self) -> None:
        episodes = reconstruct_episodes(btd_migration()).episodes
        self.assertEqual(len(episodes), 2)
        self.assertEqual(episodes[0].termination_event_id, "event-8")
        self.assertEqual(episodes[1].activation_observation.event_id, "event-8")
        self.assertEqual(episodes[1].outcome, "ONGOING")

    def test_current_active_mrz_creates_ongoing_episode(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        episode = reconstruct_episodes(rows).episodes[0]
        self.assertTrue(episode.is_ongoing)
        self.assertIsNone(episode.termination_index)

    def test_same_symbol_contributes_multiple_generations(self) -> None:
        episodes = reconstruct_episodes(btd_migration()).episodes
        self.assertEqual([item.symbol for item in episodes], ["SPXUSDT", "SPXUSDT"])
        self.assertEqual([item.generation for item in episodes], [1, 2])

    def test_deep_and_shallow_cohort_classification(self) -> None:
        rows = []
        cases = (
            ("BD", Route.BTD, ("110", "110.2", "110.4", "110.6"), Cohort.BTD_DEEP_DISCOUNT),
            ("BS", Route.BTD, ("130", "130.2", "130.4", "130.6"), Cohort.BTD_SHALLOW_DISCOUNT),
            ("SS", Route.STR, ("170", "170.2", "170.4", "170.6"), Cohort.STR_SHALLOW_PREMIUM),
            ("SD", Route.STR, ("180", "180.2", "180.4", "180.6"), Cohort.STR_DEEP_PREMIUM),
        )
        for symbol, route, prices, _cohort in cases:
            rows.extend(observation(i, price, symbol=symbol, route=route) for i, price in enumerate(prices, 1))
        episodes = reconstruct_episodes(rows).episodes
        self.assertEqual({item.symbol: item.cohort for item in episodes}, {case[0]: case[3] for case in cases})

    def test_reconstruction_uses_timestamps_not_event_id_text(self) -> None:
        rows = [
            observation(1, "110", event_id="z", observed_offset=1),
            observation(2, "110.2", event_id="y", observed_offset=2),
            observation(3, "110.4", event_id="x", observed_offset=3),
            observation(4, "110.6", event_id="a", observed_offset=4),
        ]
        self.assertEqual(reconstruct_episodes(reversed(rows)).episodes[0].activation_observation.event_id, "a")


class StructuralMeasurementTests(unittest.TestCase):
    def test_btd_and_str_route_relative_displacement_are_mirrored(self) -> None:
        btd = replay_symbol([observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]).active_mrz
        str_active = replay_symbol([
            observation(i, price, route=Route.STR)
            for i, price in enumerate(("180", "180.2", "180.4", "180.6"), 1)
        ]).active_mrz
        btd_up = observation(5, "120")
        str_up = observation(5, "190", route=Route.STR)
        self.assertEqual(route_interpretation(Route.BTD, signed_displacement(btd, btd_up)), "ROUTE_SUPPORTIVE")
        self.assertEqual(route_interpretation(Route.STR, signed_displacement(str_active, str_up)), "ROUTE_ADVERSE")

    def test_checkpoint_is_cumulative_from_activation(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6", "110.8"), 1)]
        episode = reconstruct_episodes(rows).episodes[0]
        measured = checkpoint_measurement(episode, 1)
        expected = (Decimal("0.003") + Decimal("0.005")) / Decimal("2")
        self.assertEqual(measured["signed_median_displacement"], expected)

    def test_checkpoint_denominator_shrinks_with_available_history(self) -> None:
        rows = []
        rows.extend(observation(i, price, symbol="ONE") for i, price in enumerate(("110", "110.2", "110.4", "110.6", "111"), 1))
        rows.extend(observation(i, price, symbol="TWO") for i, price in enumerate(("110", "110.2", "110.4", "110.6", "111", "111.2"), 1))
        episodes = reconstruct_episodes(rows).episodes
        self.assertEqual(aggregate_checkpoint(episodes, 1)["episodes_available"], 2)
        self.assertEqual(aggregate_checkpoint(episodes, 2)["episodes_available"], 1)

    def test_containment_uses_inclusive_core(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        active = replay_symbol(rows).active_mrz
        self.assertEqual(containment(active, observation(5, "110")), "INSIDE_MRZ")
        self.assertEqual(containment(active, observation(6, "109.9")), "BELOW_CORE")
        self.assertEqual(containment(active, observation(7, "110.7")), "ABOVE_CORE")

    def test_migration_envelope_reuses_active_mrz_tick_safeguard(self) -> None:
        rows = [observation(i, "110", tick="0.01") for i in range(1, 5)]
        rows.append(observation(5, "109.97", tick="0.01"))
        episode = reconstruct_episodes(rows).episodes[0]
        measured = checkpoint_measurement(episode, 1)
        self.assertEqual(episode.active_mrz.lower_migration_boundary, Decimal("109.98"))
        self.assertEqual(measured["below_lower_envelope"], 1)

    def test_migration_direction_and_route_relative_interpretation(self) -> None:
        btd = reconstruct_episodes(btd_migration()).episodes[0]
        self.assertEqual(btd.migration_direction, "UPWARD")
        self.assertEqual(migration_interpretation(Route.BTD, btd.migration_direction), "ROUTE_SUPPORTIVE")
        self.assertEqual(migration_interpretation(Route.BTD, "DOWNWARD"), "ROUTE_ADVERSE")
        self.assertEqual(migration_interpretation(Route.STR, "DOWNWARD"), "ROUTE_SUPPORTIVE")

    def test_successor_evaluator_is_reused_at_migration_checkpoint(self) -> None:
        first = reconstruct_episodes(btd_migration()).episodes[0]
        measured = checkpoint_measurement(first, 4)
        self.assertEqual(measured["successor_eligible_observation_count"], 4)
        self.assertTrue(measured["production_successor_evaluator_result"])
        self.assertEqual(measured["successor_candidate_lower"], Decimal("120"))
        self.assertEqual(measured["successor_candidate_upper"], Decimal("120.6"))


class DiagnosisTests(unittest.TestCase):
    def test_completed_and_ongoing_are_separated(self) -> None:
        report = cohort_report(Cohort.BTD_DEEP_DISCOUNT, reconstruct_episodes(btd_migration()).episodes)
        self.assertEqual(
            report["episode_counts"],
            {"total": 2, "completed": 1, "ongoing": 1, "unique_symbols": 1},
        )
        self.assertEqual(report["completed_episode_outcomes"]["migrated_upward"], 1)

    def test_headline_outcome_uses_completed_episodes_only(self) -> None:
        episodes = reconstruct_episodes(btd_migration()).episodes
        primary = primary_outcome_summary(Cohort.BTD_DEEP_DISCOUNT, episodes)

        self.assertEqual(primary["completed_denominator"], 1)
        self.assertEqual(primary["reversal_count"], 1)
        self.assertEqual(primary["reversal_percentage"], 100.0)
        self.assertEqual(primary["continuation_count"], 0)
        self.assertEqual(primary["unresolved_count"], 1)
        self.assertIn("Only 1 completed episode", primary["qualification"])

    def test_completed_route_adverse_btd_maps_to_downside_continuation(self) -> None:
        completed = reconstruct_episodes(btd_migration()).episodes[0]
        synthetic_adverse = replace(
            completed,
            migration_direction="DOWNWARD",
            outcome="MIGRATED_DOWNWARD",
        )
        primary = primary_outcome_summary(
            Cohort.BTD_DEEP_DISCOUNT,
            (synthetic_adverse,),
        )

        self.assertEqual(primary["continuation_label"], "Downside continuation")
        self.assertEqual(primary["continuation_count"], 1)
        self.assertEqual(primary["reversal_count"], 0)

    def test_completed_route_supportive_btd_maps_to_upward_reversal(self) -> None:
        completed = reconstruct_episodes(btd_migration()).episodes[0]
        primary = primary_outcome_summary(
            Cohort.BTD_DEEP_DISCOUNT,
            (completed,),
        )

        self.assertEqual(
            primary["reversal_label"],
            "Upward reversal / discount-long supportive",
        )
        self.assertEqual(primary["reversal_count"], 1)

    def test_str_continuation_and_reversal_language_mirrors_btd(self) -> None:
        completed = reconstruct_episodes(str_migration()).episodes[0]
        supportive = primary_outcome_summary(
            Cohort.STR_DEEP_PREMIUM,
            (completed,),
        )
        adverse = primary_outcome_summary(
            Cohort.STR_DEEP_PREMIUM,
            (replace(completed, migration_direction="UPWARD", outcome="MIGRATED_UPWARD"),),
        )

        self.assertEqual(supportive["reversal_label"], "Downward reversal / premium-short supportive")
        self.assertEqual(supportive["reversal_count"], 1)
        self.assertEqual(adverse["continuation_label"], "Upside continuation")
        self.assertEqual(adverse["continuation_count"], 1)
        self.assertEqual(
            operator_outcome_language(Cohort.STR_DEEP_PREMIUM)["adverse_meaning"],
            "Upward / against STR",
        )

    def test_intermediate_adverse_pressure_does_not_resolve_ongoing_episode(self) -> None:
        rows = [
            observation(index, price)
            for index, price in enumerate(("130", "130.2", "130.4", "130.6", "120"), 1)
        ]
        episode = reconstruct_episodes(rows).episodes[0]
        report = cohort_report(Cohort.BTD_SHALLOW_DISCOUNT, (episode,))

        self.assertTrue(episode.is_ongoing)
        self.assertEqual(report["episodes"][0]["first_adverse_pressure_observation"], 1)
        self.assertEqual(report["episodes"][0]["status"], "ONGOING")
        self.assertEqual(report["primary_outcome"]["completed_denominator"], 0)
        self.assertEqual(report["primary_outcome"]["continuation_count"], 0)
        self.assertEqual(report["primary_outcome"]["unresolved_count"], 1)

    def test_unique_symbol_breadth_is_independent_from_generation_count(self) -> None:
        rows = [*btd_migration("ONE")]
        rows.extend(
            observation(index, price, symbol="TWO")
            for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        )
        episodes = reconstruct_episodes(rows).episodes
        report = cohort_report(Cohort.BTD_DEEP_DISCOUNT, episodes)

        self.assertEqual(report["episode_counts"]["total"], 3)
        self.assertEqual(report["episode_counts"]["unique_symbols"], 2)
        self.assertEqual(
            [(item["symbol"], item["generation"]) for item in report["episodes"]],
            [("ONE", 1), ("ONE", 2), ("TWO", 1)],
        )

    def test_checkpoint_definition_is_authoritative_observations_not_bars(self) -> None:
        rows = btd_migration()
        events, active = source_rows(rows)
        report = build_feasibility_report(rows, events, active)

        self.assertIn(
            "authoritative post-activation observations",
            report["methodology"]["checkpoint_series"],
        )
        self.assertIn("never means bars", report["methodology"]["checkpoint_series"])

    def test_raw_episode_preserves_existing_values_and_adds_audit_status(self) -> None:
        first = cohort_report(
            Cohort.BTD_DEEP_DISCOUNT,
            reconstruct_episodes(btd_migration()).episodes,
        )["episodes"][0]

        self.assertEqual(first["symbol"], "SPXUSDT")
        self.assertEqual(first["generation"], 1)
        self.assertEqual(first["mrz_lower"], 110.0)
        self.assertEqual(first["mrz_upper"], 110.6)
        self.assertEqual(first["outcome"], "MIGRATED_UPWARD")
        self.assertEqual(first["route_relative_migration"], "ROUTE_SUPPORTIVE")
        self.assertEqual(first["status"], "COMPLETED")
        self.assertEqual(first["terminal_event"], "MRZ_MIGRATED")

    def test_insufficient_sample_is_prominent(self) -> None:
        episodes = reconstruct_episodes(btd_migration()).episodes
        report = cohort_report(Cohort.BTD_DEEP_DISCOUNT, episodes)
        self.assertEqual(report["diagnosis"]["status"], "Insufficient sample")
        self.assertIn("No reliable conclusion", report["diagnosis"]["activation_alone"])
        self.assertEqual(report["primary_outcome"]["sample_state"], "INSUFFICIENT SAMPLE")
        self.assertEqual(
            report["operator_interpretation"]["activation_outcome_bias"],
            "UNESTABLISHED",
        )
        self.assertEqual(
            report["candidate_confirmation_point"]["status"],
            "Not established",
        )

    def test_supportive_and_contradictory_evidence_are_both_exposed(self) -> None:
        rows = []
        for symbol_index in range(8):
            symbol = f"S{symbol_index}"
            prices = ("110", "110.2", "110.4", "110.6", "100")
            rows.extend(observation(i, price, symbol=symbol) for i, price in enumerate(prices, 1))
        report = cohort_report(Cohort.BTD_DEEP_DISCOUNT, reconstruct_episodes(rows).episodes)
        self.assertEqual(report["diagnosis"]["status"], "Pattern emerging")
        self.assertTrue(any("adverse envelope pressure" in item for item in report["diagnosis"]["contradictory_evidence"]))

    def test_mixed_activation_evidence_is_diagnosed_as_mixed(self) -> None:
        rows = []
        for symbol_index in range(8):
            symbol = f"M{symbol_index}"
            prices = (
                ("110", "110.2", "110.4", "110.6")
                if symbol_index < 4
                else ("110.2", "110.4", "110.6", "110")
            )
            rows.extend(observation(i, price, symbol=symbol) for i, price in enumerate(prices, 1))
        report = cohort_report(Cohort.BTD_DEEP_DISCOUNT, reconstruct_episodes(rows).episodes)
        self.assertEqual(report["diagnosis"]["status"], "Mixed evidence")

    def test_shallow_candidate_checkpoint_can_be_not_established(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("130", "130.2", "130.4", "130.6"), 1)]
        report = cohort_report(Cohort.BTD_SHALLOW_DISCOUNT, reconstruct_episodes(rows).episodes)
        self.assertEqual(report["diagnosis"]["candidate_confirmation_point"], "Not established")

    def test_shallow_candidate_checkpoint_is_descriptive_not_production(self) -> None:
        rows = []
        for symbol_index in range(8):
            symbol = f"C{symbol_index}"
            prices = ("129.9", "130.1", "130.3", "129.7", "129", "140", "141")
            rows.extend(observation(i, price, symbol=symbol) for i, price in enumerate(prices, 1))
        report = cohort_report(Cohort.BTD_SHALLOW_DISCOUNT, reconstruct_episodes(rows).episodes)
        self.assertEqual(report["diagnosis"]["candidate_confirmation_point"], "+3 observations")
        self.assertEqual(report["candidate_policy"]["production_status"], "NOT APPROVED")

    def test_cross_cohort_diagnosis_does_not_force_small_sample_conclusion(self) -> None:
        reports = [cohort_report(cohort, []) for cohort in Cohort]
        cross = cross_cohort_diagnosis(reports)
        self.assertEqual(cross["status"], "Insufficient sample")
        self.assertIn("insufficient", cross["overall_interpretation"].lower())

    def test_full_report_is_deterministic_and_reconciles_sources(self) -> None:
        rows = btd_migration()
        events, active = source_rows(rows)
        first = build_feasibility_report(rows, events, active)
        second = build_feasibility_report(list(reversed(rows)), events, active)
        self.assertEqual(first, second)
        self.assertTrue(first["reconstruction"]["fully_reconstructable"])
        self.assertEqual(first["reconstruction"]["total_episodes"], 2)

    def test_report_preserves_schema_and_production_boundaries(self) -> None:
        rows = btd_migration()
        events, active = source_rows(rows)
        report = build_feasibility_report(rows, events, active)
        self.assertEqual(report["invariants"]["schema_version"], "4.3 unchanged")
        self.assertEqual(report["invariants"]["mrz_engine_behavior"], "unchanged")
        self.assertEqual(report["invariants"]["operation_card_trading_window_state"], "not implemented")
        self.assertNotIn("trading_window", report["cohorts"][0]["episodes"][0])


if __name__ == "__main__":
    unittest.main()
