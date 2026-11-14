from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from app.domain import MRZEventType, Route
from app.mrz_evidence import build_post_activation_evidence
from app.mrz_robustness import post_activation_snapshot
from app.opportunity_intelligence import (
    _mrz_lifecycles,
    build_canonical_opportunity_evidence,
)
from app.pressure_notifications import PressureNotificationCoordinator
from app.state_engine import replay_symbol
from tests.helpers import BASE_TIME, observation
from tests.test_opportunity_intelligence import at, nbis_inputs


class PressureIsolationTests(unittest.TestCase):
    def test_canonical_replay_does_not_invoke_pressure_classifiers(self) -> None:
        rows = tuple(
            observation(index, price)
            for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        ) + tuple(
            observation(index, price, route=Route.STR)
            for index, price in enumerate(("180", "180.2", "180.4", "180.6"), 5)
        )

        with patch(
            "app.pressure.classify_current_pressure_directions",
            side_effect=AssertionError("Pressure must not participate in MRZ replay"),
        ), patch(
            "app.pressure.classify_cumulative_pressure",
            side_effect=AssertionError("Pressure must not participate in MRZ replay"),
        ):
            result = replay_symbol(rows)

        self.assertEqual(
            [transition.event_type for transition in result.transitions],
            [
                MRZEventType.ACTIVATED,
                MRZEventType.MIGRATED,
                MRZEventType.ROUTE_CHANGED,
            ],
        )
        self.assertEqual(result.active_mrz.route_owner, Route.STR)
        self.assertEqual(result.active_mrz.activation_event_id, "event-8")
        self.assertEqual(
            [transition.trigger_event_id for transition in result.transitions],
            ["event-4", "event-8", "event-8"],
        )
        self.assertEqual(result.transitions[1].details["external_side"], "UP")

    def test_factual_evidence_is_available_without_pressure_interpretation(self) -> None:
        formation = tuple(
            observation(index, price)
            for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        )
        active = replay_symbol(formation).active_mrz
        post_activation = (
            observation(5, "110.3"),
            observation(6, "120"),
            observation(7, "100"),
        )

        with patch(
            "app.pressure.classify_cumulative_pressure",
            side_effect=AssertionError("factual evidence must remain Pressure-neutral"),
        ):
            evidence = build_post_activation_evidence(
                active, (*formation, *post_activation)
            )

        self.assertEqual(evidence.total_observation_count, 3)
        self.assertEqual(evidence.inside_mrz_count, 1)
        self.assertEqual(evidence.above_mrz_count, 1)
        self.assertEqual(evidence.below_mrz_count, 1)
        self.assertEqual(evidence.above_envelope_count, 1)
        self.assertEqual(evidence.below_envelope_count, 1)
        self.assertEqual(
            [(item.observation.event_id, item.side) for item in evidence.external_observations],
            [("event-6", "UP"), ("event-7", "DOWN")],
        )

    def test_pressure_snapshot_preserves_latest_four_and_cumulative_policy(self) -> None:
        formation = tuple(
            observation(index, price)
            for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        )
        active = replay_symbol(formation).active_mrz
        pressure_rows = tuple(
            observation(index, price)
            for index, price in enumerate(("120", "121", "122", "100"), 5)
        )

        snapshot = post_activation_snapshot(active, (*formation, *pressure_rows))

        self.assertEqual(snapshot.above_envelope_count, 3)
        self.assertEqual(snapshot.below_envelope_count, 1)
        self.assertEqual(snapshot.state.direction, "UP")
        self.assertEqual(snapshot.state.label, "Upward Pressure")
        self.assertEqual(snapshot.current_pressure.state.direction, "UP")
        self.assertEqual(snapshot.current_pressure.recent_higher_count, 3)
        self.assertEqual(snapshot.current_pressure.recent_lower_count, 1)
        self.assertEqual(
            [item.direction for item in snapshot.current_pressure.recent_evidence],
            ["UP", "UP", "UP", "DOWN"],
        )

    def test_canonical_opportunity_evidence_does_not_require_pressure_projection(self) -> None:
        inputs = nbis_inputs()
        cursor = at("2026-11-12T00:00:00Z")

        with patch(
            "app.opportunity_intelligence.build_opportunity_pressure_projection",
            side_effect=AssertionError("canonical opportunity evidence is independent"),
        ):
            canonical = build_canonical_opportunity_evidence(inputs, "NBIS", cursor)

        self.assertIsNotNone(canonical)
        self.assertEqual(len(canonical["observation_events"]), 14)
        self.assertEqual(len(canonical["lifecycles"]), 1)
        self.assertEqual(len(canonical["near_misses"]), 2)
        self.assertEqual(
            [item["canonical_event_id"] for item in canonical["observation_events"]],
            [item.event_id for item in inputs["observations"]],
        )

    def test_pressure_notification_projection_can_be_absent(self) -> None:
        writer = Mock()
        PressureNotificationCoordinator(None, writer).reconcile("event-9")
        writer.assert_not_called()

    def test_existing_xau_knowledge_time_defect_remains_explicit(self) -> None:
        inputs = nbis_inputs()
        event = dict(inputs["mrz_events"][0])
        event.update(
            symbol="XAUUSD",
            event_key="XAUUSD:1:MRZ_ACTIVATED:xau-trigger",
            trigger_event_id="xau-trigger",
            trigger_received_at=BASE_TIME + timedelta(minutes=1),
            occurred_at=BASE_TIME,
        )
        required_support_received_at = BASE_TIME + timedelta(hours=2)

        lifecycle = _mrz_lifecycles((event,))[0]

        # This deliberately records the pre-existing defect: reconstructed MRZ
        # knowledge time uses only the trigger receipt and can precede receipt of
        # another required supporting observation. Remediation is outside Phase 1.
        self.assertLess(
            at(lifecycle["known_at"]),
            required_support_received_at,
        )


if __name__ == "__main__":
    unittest.main()
