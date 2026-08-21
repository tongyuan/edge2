from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain import MRZEventType, Route, StructuralLocation
from app.state_engine import replay_symbol
from tests.helpers import observation


class ActiveMRZStateTests(unittest.TestCase):
    def test_initial_state_is_unestablished_until_fourth_observation(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4"), 1)]
        self.assertIsNone(replay_symbol(rows).active_mrz)
        rows.append(observation(4, "110.6"))
        result = replay_symbol(rows)
        self.assertEqual(result.active_mrz.route_owner, Route.BTD)
        self.assertEqual(result.active_mrz.activation_event_id, "event-4")
        self.assertEqual(result.active_mrz.confirming_observation_count, 4)
        self.assertEqual(result.active_mrz.supporting_observation_count, 4)
        self.assertEqual(result.transitions[0].event_type, MRZEventType.ACTIVATED)

    def test_same_route_structural_observations_inside_frozen_core_accumulate_support(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        activated = replay_symbol(rows).active_mrz
        rows.extend((observation(5, "110.3"), observation(6, "110.5")))
        supported = replay_symbol(rows).active_mrz

        self.assertEqual(supported.supporting_observation_count, 6)
        self.assertEqual(supported.confirming_observation_count, 4)
        self.assertEqual(
            (supported.core_mrz_lower, supported.core_mrz_upper),
            (activated.core_mrz_lower, activated.core_mrz_upper),
        )

    def test_outside_core_envelope_and_successor_observations_do_not_support_active_mrz(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.extend(
            (
                observation(5, "111"),
                observation(6, "111.7"),
                observation(7, "120"),
            )
        )
        active = replay_symbol(rows).active_mrz

        self.assertEqual(active.upper_migration_boundary, Decimal("111.8"))
        self.assertEqual(active.supporting_observation_count, 4)

    def test_opposite_route_observation_does_not_support_active_mrz(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.append(observation(5, "180", route=Route.STR))
        self.assertEqual(replay_symbol(rows).active_mrz.supporting_observation_count, 4)

    def test_inside_core_observation_must_remain_structurally_eligible(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.append(observation(5, "110.3", ipda_low="0", ipda_high="120"))
        self.assertEqual(replay_symbol(rows).active_mrz.supporting_observation_count, 4)

    def test_bounds_freeze_after_activation_and_inside_envelope_observation(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        active = replay_symbol(rows).active_mrz
        rows.extend((observation(5, "110.8"), observation(6, "112")))
        later = replay_symbol(rows).active_mrz
        self.assertEqual((later.core_mrz_lower, later.core_mrz_upper), (active.core_mrz_lower, active.core_mrz_upper))
        self.assertEqual(len(replay_symbol(rows).transitions), 1)

    def test_btd_requires_four_external_concentrated_observations_to_migrate(self) -> None:
        base = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        fewer = base + [observation(5, "120"), observation(6, "120.2"), observation(7, "120.4")]
        self.assertEqual(replay_symbol(fewer).active_mrz.core_mrz_lower, Decimal("110"))
        migrated = replay_symbol(fewer + [observation(8, "120.6")])
        self.assertEqual(migrated.active_mrz.core_mrz_lower, Decimal("120"))
        self.assertEqual(migrated.active_mrz.core_mrz_upper, Decimal("120.6"))
        self.assertEqual(migrated.transitions[-1].event_type, MRZEventType.MIGRATED)
        self.assertEqual(migrated.transitions[-1].old_mrz.core_mrz_lower, Decimal("110"))

    def test_migration_resets_support_to_successor_confirming_cluster(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.extend((observation(5, "110.3"), observation(6, "110.5")))
        before = replay_symbol(rows).active_mrz
        rows.extend(
            observation(i, price)
            for i, price in enumerate(("120", "120.2", "120.4", "120.6"), 7)
        )
        migrated = replay_symbol(rows)

        self.assertEqual(before.supporting_observation_count, 6)
        self.assertEqual(migrated.transitions[-1].old_mrz.supporting_observation_count, 6)
        self.assertEqual(migrated.active_mrz.supporting_observation_count, 4)
        self.assertEqual(migrated.active_mrz.confirming_observation_count, 4)

    def test_str_mirror_migrates_below_lower_envelope(self) -> None:
        prices = ("180", "180.2", "180.4", "180.6", "170.6", "170.4", "170.2", "170")
        rows = [observation(i, price, route=Route.STR) for i, price in enumerate(prices, 1)]
        result = replay_symbol(rows)
        self.assertEqual(result.active_mrz.route_owner, Route.STR)
        self.assertEqual(result.active_mrz.core_mrz_lower, Decimal("170"))
        self.assertEqual(result.active_mrz.structural_location, StructuralLocation.SHALLOW_PREMIUM)

    def test_inside_envelope_observations_do_not_contribute_to_successor(self) -> None:
        prices = ("110", "110.2", "110.4", "110.6", "111", "111.2", "111.4", "111.6")
        rows = [observation(i, price) for i, price in enumerate(prices, 1)]
        result = replay_symbol(rows)
        self.assertEqual(len(result.transitions), 1)
        self.assertEqual(result.active_mrz.core_mrz_lower, Decimal("110"))

    def test_inside_envelope_events_age_old_successor_evidence_out(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.extend([observation(5, "120"), observation(6, "120.2"), observation(7, "120.4")])
        for index in range(8, 25):
            rows.append(observation(index, "111"))
        rows.append(observation(25, "120.6"))
        result = replay_symbol(rows)
        self.assertEqual(len(result.transitions), 1)
        self.assertEqual(result.active_mrz.core_mrz_lower, Decimal("110"))

    def test_rolling_window_aging_does_not_reduce_cumulative_active_support(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.extend(observation(index, "110.3") for index in range(5, 30))
        active = replay_symbol(rows).active_mrz

        self.assertEqual(active.supporting_observation_count, 29)
        self.assertEqual(active.confirming_observation_count, 4)

    def test_zero_width_mrz_uses_tick_safeguard(self) -> None:
        rows = [observation(i, "110", tick="0.01") for i in range(1, 5)]
        active = replay_symbol(rows).active_mrz
        self.assertEqual(active.width, Decimal("0"))
        self.assertEqual(active.effective_width, Decimal("0.01"))
        self.assertEqual(active.lower_migration_boundary, Decimal("109.98"))
        self.assertEqual(active.upper_migration_boundary, Decimal("110.02"))

    def test_opposite_route_concentration_does_not_invent_route_change(self) -> None:
        rows = [observation(i, price) for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)]
        rows.extend(
            observation(i, price, route=Route.STR)
            for i, price in enumerate(("180", "180.2", "180.4", "180.6"), 5)
        )
        result = replay_symbol(rows)
        self.assertEqual(result.active_mrz.route_owner, Route.BTD)
        self.assertEqual(len(result.transitions), 1)

    def test_replay_uses_timestamps_not_event_id_names(self) -> None:
        rows = [
            observation(1, "110", event_id="2099_future_name", observed_offset=1, received_offset=9),
            observation(2, "110.2", event_id="0001_past_name", observed_offset=2, received_offset=8),
            observation(3, "110.4", event_id="z_name", observed_offset=3, received_offset=7),
            observation(4, "110.6", event_id="a_name", observed_offset=4, received_offset=6),
        ]
        result = replay_symbol(reversed(rows))
        self.assertEqual(result.active_mrz.activation_event_id, "a_name")

    def test_structurally_invalid_cluster_does_not_activate(self) -> None:
        btd_premium = [observation(i, price) for i, price in enumerate(("180", "180.2", "180.4", "180.6"), 1)]
        str_discount = [
            observation(i, price, route=Route.STR)
            for i, price in enumerate(("110", "110.2", "110.4", "110.6"), 1)
        ]
        self.assertIsNone(replay_symbol(btd_premium).active_mrz)
        self.assertIsNone(replay_symbol(str_discount).active_mrz)
