from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.db import connect
from app.domain import Route
from app.mrz_robustness import MRZRobustnessService
from app.repository import EdgeRepository
from app.state_engine import replay_symbol
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.helpers import BASE_TIME, observation


FIXED_NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def report_for(
    post_activation_rows=(),
    *,
    active_route=Route.BTD,
    formation_prices=None,
    migration=None,
):
    formation_prices = formation_prices or (
        ("110", "110.2", "110.4", "110.6")
        if active_route is Route.BTD
        else ("180", "180.2", "180.4", "180.6")
    )
    formation = tuple(
        observation(index, price, route=active_route)
        for index, price in enumerate(formation_prices, 1)
    )
    active = replay_symbol(formation).active_mrz
    rows = (*formation, *post_activation_rows)
    report = MRZRobustnessService(
        lambda: (
            (active,),
            rows,
            {active.symbol: migration or {"has_migrated": False}},
        ),
        clock=lambda: FIXED_NOW,
    ).generate_report()
    return active, report["active_mrzs"][0]


class MRZRobustnessTests(unittest.TestCase):
    def test_only_canonical_post_activation_observations_are_included(self) -> None:
        post = (
            observation(5, "110.3", observed_offset=5),
            observation(6, "111", observed_offset=6),
        )
        active, report = report_for(post)

        self.assertEqual(active.activation_event_id, "event-4")
        self.assertEqual(report["active_mrz"]["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(report["formation_evidence"]["confirming_observation_count"], 4)
        self.assertEqual(report["robustness_evidence"]["post_activation_observation_count"], 2)
        self.assertEqual(report["containment"]["total_observation_count"], 2)

    def test_containment_boundary_pressure_and_signed_midpoint_displacement(self) -> None:
        post = (
            observation(5, "110", observed_offset=5),
            observation(6, "110.3", observed_offset=6),
            observation(7, "110.6", observed_offset=7),
            observation(8, "111", observed_offset=8),
        )
        _active, report = report_for(post)

        self.assertEqual(report["containment"]["inside_observation_count"], 3)
        self.assertEqual(report["containment"]["total_observation_count"], 4)
        self.assertEqual(report["containment"]["percentage"], "75")
        self.assertEqual(report["boundary_pressure"]["upper_boundary_test_count"], 2)
        self.assertEqual(report["boundary_pressure"]["lower_boundary_test_count"], 1)
        self.assertEqual(report["boundary_pressure"]["outside_envelope_observation_count"], 0)
        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "0.150",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "ABOVE")
        self.assertEqual(
            report["mrz_displacement"]["normalization"],
            "Normalized by full IPDA 20W width stored at activation.",
        )

    def test_all_observations_above_midpoint_have_positive_displacement(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("111", "112", "113"), 5)
        )
        _active, report = report_for(post)

        displacement = report["mrz_displacement"]
        self.assertEqual(
            displacement[
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "1.700",
        )
        self.assertEqual(displacement["direction"], "ABOVE")
        self.assertEqual(displacement["label"], "Median displacement above midpoint")

    def test_all_observations_below_midpoint_have_negative_displacement(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("109", "108", "107"), 5)
        )
        _active, report = report_for(post)

        displacement = report["mrz_displacement"]
        self.assertEqual(
            displacement[
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "-2.300",
        )
        self.assertEqual(displacement["direction"], "BELOW")
        self.assertEqual(displacement["label"], "Median displacement below midpoint")

    def test_one_observation_uses_signed_full_ipda_normalization_without_pressure(self) -> None:
        _active, report = report_for(
            (observation(5, "111.3", observed_offset=5),),
        )

        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "1.00",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "ABOVE")
        self.assertEqual(report["migration_pressure"]["status"], "STABLE")
        self.assertEqual(
            report["successor_watch"]["status"],
            "NO_SUCCESSOR_CANDIDATE",
        )

    def test_displacement_that_rounds_to_zero_is_centered(self) -> None:
        _active, report = report_for(
            (observation(5, "110.34", observed_offset=5),),
        )

        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "0.0400",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "CENTERED")
        self.assertEqual(report["mrz_displacement"]["label"], "Centered around midpoint")

    def test_mixed_sample_preserves_sign_before_median(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("105.3", "108.3", "111.3", "117.3"), 5)
        )
        _active, report = report_for(post)

        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "-0.50",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "BELOW")

    def test_symmetric_sample_is_centered_around_midpoint(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("105.3", "108.3", "112.3", "115.3"), 5)
        )
        _active, report = report_for(post)

        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "0.00",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "CENTERED")
        self.assertEqual(report["mrz_displacement"]["label"], "Centered around midpoint")
        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertEqual(report["successor_watch"]["status"], "CANDIDATE_FORMING")

    def test_median_displacement_resists_one_extreme_outlier(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("110.4", "110.5", "110.6", "190.3"), 5)
        )
        _active, report = report_for(post)

        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "0.250",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "ABOVE")

    def test_route_integrity_uses_owner_route_and_current_observation_ipda(self) -> None:
        maintained = (
            observation(5, "110.3", observed_offset=5),
            observation(6, "111", observed_offset=6),
        )
        _active, maintained_report = report_for(maintained)
        self.assertEqual(maintained_report["route_integrity"]["status"], "MAINTAINED")
        self.assertEqual(
            maintained_report["route_integrity"]["label"],
            "Discount structure maintained",
        )

        mixed = (*maintained, observation(7, "180", route=Route.STR, observed_offset=7))
        _active, mixed_report = report_for(mixed)
        self.assertEqual(mixed_report["route_integrity"]["status"], "MIXED")
        self.assertEqual(mixed_report["route_integrity"]["opposite_route_observation_count"], 1)

    def test_external_observations_create_pressure_without_confirming_successor(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("120", "120.2", "120.4"), 5)
        )
        active, report = report_for(post)

        self.assertEqual(active.upper_migration_boundary, Decimal("111.8"))
        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["migration_pressure"]["direction"], "UP")
        self.assertEqual(report["migration_pressure"]["direction_label"], "Upward")
        self.assertEqual(report["migration_pressure"]["relevant_boundary"], "111.8")
        self.assertEqual(report["migration_pressure"]["observations_beyond_envelope"], 3)
        self.assertEqual(report["post_activation_robustness"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["structural_authority"]["label"], "Authoritative")
        self.assertEqual(report["successor_watch"]["status"], "AWAITING_CONFIRMATION")
        self.assertEqual(report["successor_watch"]["direction"], "UP")
        self.assertEqual(report["successor_watch"]["direction_label"], "Higher MRZ")
        self.assertEqual(report["successor_watch"]["evidence_observation_count"], 3)
        self.assertEqual(report["successor_watch"]["required_observation_count"], 4)
        self.assertTrue(report["migration_pressure"]["current_mrz_remains_authoritative"])

    def test_candidate_forming_and_all_classifications_are_deterministic(self) -> None:
        formation = tuple(
            observation(index, price)
            for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        )
        post = (
            observation(5, "120", observed_offset=5),
            observation(6, "120.2", observed_offset=6),
        )
        active = replay_symbol(formation).active_mrz
        service = MRZRobustnessService(
            lambda: (
                (active,),
                (*formation, *post),
                {active.symbol: {"has_migrated": False}},
            ),
            clock=lambda: FIXED_NOW,
        )

        first = service.generate_report()
        second = service.generate_report()
        report = first["active_mrzs"][0]

        self.assertEqual(first, second)
        self.assertEqual(report["successor_watch"]["status"], "CANDIDATE_FORMING")
        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["post_activation_robustness"]["status"], "UNDER_PRESSURE")

    def test_confirmed_successor_is_diagnostic_and_does_not_replace_active_mrz(self) -> None:
        post = tuple(
            observation(index, price, observed_offset=index)
            for index, price in enumerate(("120", "120.2", "120.4", "120.6"), 5)
        )
        active, report = report_for(post)

        self.assertEqual(report["migration_pressure"]["status"], "MIGRATION_CANDIDATE")
        self.assertEqual(report["successor_watch"]["status"], "CONFIRMED_SUCCESSOR")
        self.assertEqual(report["successor_watch"]["candidate_lower"], "120")
        self.assertEqual(report["successor_watch"]["candidate_upper"], "120.6")
        self.assertEqual(report["successor_watch"]["normalized_span"], "0.006")
        self.assertTrue(report["successor_watch"]["diagnostic_only"])
        self.assertEqual(active.core_mrz_lower, Decimal("110"))
        self.assertEqual(active.activation_event_id, "event-4")

    def test_str_route_uses_lower_directional_successor_and_premium_integrity(self) -> None:
        post = tuple(
            observation(index, price, route=Route.STR, observed_offset=index)
            for index, price in enumerate(("170.6", "170.4", "170.2"), 5)
        )
        _active, report = report_for(post, active_route=Route.STR)

        self.assertEqual(report["route_integrity"]["label"], "Premium structure maintained")
        self.assertEqual(report["successor_watch"]["status"], "AWAITING_CONFIRMATION")
        self.assertEqual(report["successor_watch"]["route"], "STR")
        self.assertEqual(report["migration_pressure"]["direction"], "DOWN")
        self.assertEqual(report["migration_pressure"]["direction_label"], "Downward")
        self.assertEqual(report["successor_watch"]["direction_label"], "Lower MRZ")

    def test_empty_active_set_and_newly_activated_mrz_are_neutral(self) -> None:
        empty = MRZRobustnessService(
            lambda: ((), (), {}),
            clock=lambda: FIXED_NOW,
        ).generate_report()
        self.assertEqual(empty["active_mrz_count"], 0)
        self.assertEqual(empty["active_mrzs"], [])

        _active, report = report_for(())
        self.assertEqual(report["migration_pressure"]["status"], "NO_EVIDENCE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertEqual(
            report["post_activation_robustness"]["status"],
            "NOT_YET_ASSESSABLE",
        )
        self.assertEqual(
            report["post_activation_robustness"]["label"],
            "Not yet assessable",
        )
        self.assertEqual(report["successor_watch"]["status"], "NO_SUCCESSOR_CANDIDATE")
        self.assertEqual(report["containment"]["percentage"], None)
        self.assertEqual(report["migration"], {"has_migrated": False})
        self.assertIsNone(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ]
        )
        self.assertIsNone(report["mrz_displacement"]["direction"])
        self.assertEqual(
            report["mrz_displacement"]["label"],
            "No post-activation evidence",
        )

    def test_migration_provenance_remains_visible_when_current_state_is_stable(self) -> None:
        migration = {
            "has_migrated": True,
            "direction": "UP",
            "migrated_at": "2026-08-24T16:00:00Z",
            "previous_lower": 0.3936,
            "previous_upper": 0.3966,
            "current_lower": 0.4034,
            "current_upper": 0.4083,
            "route_owner": "BTD",
            "migration_event_id": "wld-migration",
        }
        _active, report = report_for(
            (observation(5, "110.3", observed_offset=5),),
            migration=migration,
        )

        self.assertEqual(report["migration"], migration)
        self.assertEqual(report["migration_pressure"]["status"], "STABLE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertEqual(report["post_activation_robustness"]["status"], "STABLE")
        self.assertEqual(
            report["successor_watch"]["status"],
            "NO_SUCCESSOR_CANDIDATE",
        )

    def test_downward_migration_direction_is_preserved(self) -> None:
        migration = {
            "has_migrated": True,
            "direction": "DOWN",
            "migrated_at": "2026-08-24T17:00:00Z",
            "previous_lower": 180.0,
            "previous_upper": 180.6,
            "current_lower": 170.0,
            "current_upper": 170.6,
            "route_owner": "STR",
            "migration_event_id": "str-migration",
        }
        _active, report = report_for(
            (),
            active_route=Route.STR,
            migration=migration,
        )

        self.assertEqual(report["migration"]["direction"], "DOWN")

    def test_all_exact_structural_locations_and_roles_are_exposed(self) -> None:
        cases = (
            (Route.BTD, ("110", "110.2", "110.4", "110.6"), "Deep Discount", "Supportive"),
            (Route.BTD, ("130", "130.2", "130.4", "130.6"), "Shallow Discount", "Supportive"),
            (Route.STR, ("160", "160.2", "160.4", "160.6"), "Shallow Premium", "Resistive"),
            (Route.STR, ("180", "180.2", "180.4", "180.6"), "Deep Premium", "Resistive"),
        )
        for route, prices, location, role in cases:
            with self.subTest(route=route, location=location):
                _active, report = report_for(
                    (),
                    active_route=route,
                    formation_prices=prices,
                )
                self.assertEqual(
                    report["structural_authority"]["structural_location_label"],
                    location,
                )
                self.assertEqual(
                    report["structural_authority"]["structural_role_label"],
                    role,
                )

    def test_stable_behavior_has_neutral_pressure_with_factual_sample(self) -> None:
        _active, report = report_for(
            (observation(5, "110.3", observed_offset=5),),
        )

        self.assertEqual(report["post_activation_robustness"]["status"], "STABLE")
        self.assertEqual(
            report["post_activation_robustness"][
                "post_activation_observation_count"
            ],
            1,
        )
        self.assertEqual(report["migration_pressure"]["status"], "STABLE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertIsNone(report["migration_pressure"]["relevant_boundary"])

    def test_pressure_without_successor_retains_directional_evidence(self) -> None:
        opposite_route_pressure = (
            observation(5, "180", route=Route.STR, observed_offset=5),
        )
        _active, report = report_for(opposite_route_pressure)

        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["migration_pressure"]["direction"], "UP")
        self.assertEqual(
            report["successor_watch"]["status"],
            "NO_SUCCESSOR_CANDIDATE",
        )
        self.assertEqual(
            report["structural_summary"]["successor_label"],
            "Not confirmed",
        )

    def test_balanced_external_evidence_is_neutral_without_hiding_pressure(self) -> None:
        balanced_pressure = (
            observation(5, "120", observed_offset=5),
            observation(6, "100", observed_offset=6),
        )
        _active, report = report_for(balanced_pressure)

        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertEqual(report["migration_pressure"]["observations_beyond_envelope"], 2)
        self.assertIn(
            "without a dominant direction",
            report["structural_summary"]["detail_statement"],
        )


class MRZRobustnessDatabaseSafetyTests(unittest.TestCase):
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

    def ingest(self, index: int, price: str) -> None:
        payload = ObservationPayload.model_validate({
            "schema_version": "4.3",
            "event_id": f"robustness-db-{index}",
            "symbol": "SPXUSDT",
            "route": "BTD",
            "observation_type": "reclaim",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME.replace(second=index),
        })
        self.repository.ingest(payload, Decimal("0.01"))

    def test_generating_report_does_not_mutate_operational_state(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6", "120"), 1):
            self.ingest(index, price)

        before = self.snapshot()
        report = MRZRobustnessService(
            self.repository.mrz_robustness_inputs,
            clock=lambda: FIXED_NOW,
        ).generate_report()
        after = self.snapshot()

        self.assertEqual(before, after)
        self.assertEqual(report["active_mrz_count"], 1)
        self.assertEqual(report["active_mrzs"][0]["migration_pressure"]["status"], "UNDER_PRESSURE")

    def test_report_is_identical_after_repository_restart(self) -> None:
        for index, price in enumerate(
            ("110", "110.2", "110.4", "110.6", "120", "120.2"),
            1,
        ):
            self.ingest(index, price)

        before_restart = MRZRobustnessService(
            self.repository.mrz_robustness_inputs,
            clock=lambda: FIXED_NOW,
        ).generate_report()
        restarted_repository = EdgeRepository(self.database_url)
        after_restart = MRZRobustnessService(
            restarted_repository.mrz_robustness_inputs,
            clock=lambda: FIXED_NOW,
        ).generate_report()

        self.assertEqual(before_restart, after_restart)
        self.assertEqual(
            before_restart["active_mrzs"][0]["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "9.800",
        )
