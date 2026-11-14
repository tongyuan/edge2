from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.domain import Observation, ObservationType, Route
from app.opportunity_intelligence import (
    build_opportunity_overview,
    build_symbol_opportunity,
)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def observation(
    identifier: int,
    event_id: str,
    route: Route,
    price: str,
    observed_at: str,
    *,
    received_at: str | None = None,
    low: str = "145.80",
    high: str = "299.86",
) -> Observation:
    return Observation(
        id=identifier,
        event_id=event_id,
        schema_version="4.3",
        symbol="NBIS",
        route=route,
        observation_type=(
            ObservationType.RECLAIM
            if route is Route.BTD
            else ObservationType.REJECTION
        ),
        observation_price=Decimal(price),
        observation_price_tick=Decimal("0.01"),
        ipda_20w_high=Decimal(high),
        ipda_20w_low=Decimal(low),
        observed_at=at(observed_at),
        received_at=at(received_at or observed_at),
    )


def nbis_inputs() -> dict:
    observations = (
        observation(1, "nbis-aug21-str", Route.STR, "224.51", "2026-08-21T15:48:00Z"),
        observation(2, "nbis-sep09-str", Route.STR, "243.62", "2026-09-09T18:51:00Z"),
        observation(3, "nbis-sep11-str", Route.STR, "227.73", "2026-09-11T17:48:00Z"),
        observation(4, "nbis-sep14-btd", Route.BTD, "214.00", "2026-09-14T15:33:00Z"),
        observation(5, "nbis-sep18-btd", Route.BTD, "215.44", "2026-09-18T13:51:00Z"),
        observation(6, "nbis-sep22-str", Route.STR, "242.19", "2026-09-22T14:09:00Z"),
        observation(7, "nbis-oct02-near", Route.STR, "243.73", "2026-10-02T15:20:00Z"),
        observation(
            8,
            "nbis-oct02-activation",
            Route.STR,
            "242.89",
            "2026-10-02T19:57:00Z",
            received_at="2026-10-02T19:57:03Z",
        ),
        observation(9, "nbis-oct06-higher", Route.STR, "252.90", "2026-10-06T17:47:00Z"),
        observation(10, "nbis-oct09-lower-1", Route.BTD, "220.24", "2026-10-09T13:48:00Z"),
        observation(11, "nbis-oct09-lower-2", Route.BTD, "220.85", "2026-10-09T18:06:00Z"),
        observation(12, "nbis-oct13-lower", Route.BTD, "201.21", "2026-10-13T14:11:00Z"),
        observation(13, "nbis-oct15-lower", Route.BTD, "170.35", "2026-10-15T14:41:00Z"),
        observation(
            14,
            "nbis-nov10-lower",
            Route.BTD,
            "139.50",
            "2026-11-10T14:35:00Z",
            low="113.30",
            high="290.60",
        ),
    )
    mrz_events = (
        {
            "event_key": "NBIS:1:MRZ_ACTIVATED:nbis-oct02-activation",
            "sequence": 1,
            "event_type": "MRZ_ACTIVATED",
            "symbol": "NBIS",
            "route_owner": "STR",
            "previous_route_owner": None,
            "occurred_at": at("2026-10-02T19:57:00Z"),
            "trigger_event_id": "nbis-oct02-activation",
            "trigger_received_at": at("2026-10-02T19:57:03Z"),
            "old_core_mrz_lower": None,
            "old_core_mrz_upper": None,
            "new_core_mrz_lower": Decimal("242.19"),
            "new_core_mrz_upper": Decimal("243.73"),
            "new_core_mrz_midpoint": Decimal("242.96"),
            "structural_location": "shallow_premium_core_mrz",
            "confirming_observation_count": 4,
            "new_supporting_observation_count": 4,
            "activation_source": "PRODUCTION_QUALIFIED",
            "instrument_tick": Decimal("0.01"),
            "details": {},
        },
    )
    near_misses = (
        {
            "id": 208,
            "episode_key": "nbis-btd-near",
            "symbol": "NBIS",
            "route_owner": "BTD",
            "started_at": at("2026-09-18T13:51:07Z"),
            "ended_at": at("2026-10-02T19:57:04Z"),
            "ended_reason": "SYMBOL_ACTIVATED",
            "canonical_candidate_identity": "a" * 64,
            "canonical_candidate_event_id": "nbis-sep18-btd",
            "canonical_candidate_lower": Decimal("214.00"),
            "canonical_candidate_upper": Decimal("217.02"),
            "canonical_candidate_midpoint": Decimal("215.51"),
            "canonical_structural_location": "shallow_discount_core_mrz",
            "canonical_supporting_observation_count": 4,
            "canonical_supporting_observation_ids": [
                "nbis-sep14-btd",
                "nbis-sep18-btd",
                "earlier-btd-a",
                "earlier-btd-b",
            ],
            "canonical_candidate_timestamp": at("2026-09-18T13:51:00Z"),
            "canonical_snapshot_reliable": True,
        },
        {
            "id": 250,
            "episode_key": "nbis-str-near",
            "symbol": "NBIS",
            "route_owner": "STR",
            "started_at": at("2026-10-02T15:20:04Z"),
            "ended_at": at("2026-10-02T19:57:04Z"),
            "ended_reason": "SYMBOL_ACTIVATED",
            "canonical_candidate_identity": "b" * 64,
            "canonical_candidate_event_id": "nbis-oct02-near",
            "canonical_candidate_lower": Decimal("241.16"),
            "canonical_candidate_upper": Decimal("243.73"),
            "canonical_candidate_midpoint": Decimal("242.445"),
            "canonical_structural_location": "shallow_premium_core_mrz",
            "canonical_supporting_observation_count": 4,
            "canonical_supporting_observation_ids": [
                "nbis-sep09-str",
                "nbis-sep22-str",
                "nbis-oct02-near",
                "earlier-str",
            ],
            "canonical_candidate_timestamp": at("2026-10-02T15:20:00Z"),
            "canonical_snapshot_reliable": True,
        },
    )
    return {
        "as_of": at("2026-11-12T00:00:00Z"),
        "groups": [
            {"id": 5, "name": "My Port", "members": ["NBIS"]},
            {"id": 21, "name": "AI Clouds", "members": ["NBIS"]},
        ],
        "observations": observations,
        "mrz_events": mrz_events,
        "near_miss_episodes": near_misses,
        "current_pressure_events": (),
    }


class OpportunityIntelligenceTests(unittest.TestCase):
    def test_nbis_reconstruction_preserves_structure_and_conflict(self) -> None:
        detail = build_symbol_opportunity(nbis_inputs(), "NBIS")
        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["episodes"]), 2)
        str_episode = next(
            item for item in detail["episodes"] if item["hypothesis"] == "STR"
        )
        self.assertEqual(str_episode["state"], "STRUCTURE_ESTABLISHED")
        self.assertGreater(str_episode["conflicting_evidence_count"], 0)
        self.assertEqual(str_episode["entry_verification"]["status"], "NOT_VERIFIED")
        self.assertEqual(len(detail["near_miss_events"]), 2)
        mrz = detail["mrz_lifecycles"][0]
        self.assertEqual(mrz["lower_bound"], "242.19")
        self.assertEqual(mrz["upper_bound"], "243.73")
        self.assertEqual(mrz["lower_migration_boundary"], "239.11")
        self.assertEqual(mrz["upper_migration_boundary"], "246.81")
        self.assertEqual(detail["pressure_observations"], [])
        self.assertEqual(len(detail["observations"]), 14)
        self.assertEqual(detail["pressure_retirement"]["status"], "retired")
        self.assertEqual(detail["persisted_current_pressure_events"], [])
        self.assertEqual(detail["ote"]["status"], "not_connected")

    def test_replay_does_not_back_project_future_mrz(self) -> None:
        inputs = nbis_inputs()
        september = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2026-09-11T23:59:59Z")
        )
        self.assertEqual(september["mrz_lifecycles"], [])
        self.assertEqual(september["near_miss_events"], [])
        self.assertEqual(september["pressure_observations"], [])
        self.assertEqual(september["episodes"][0]["state"], "CONTEXT_OBSERVED")

        pre_activation = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2026-10-02T15:20:05Z")
        )
        self.assertEqual(pre_activation["mrz_lifecycles"], [])
        self.assertEqual(
            next(
                item
                for item in pre_activation["episodes"]
                if item["hypothesis"] == "STR"
            )["state"],
            "NEAR_MISS",
        )

        established = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2026-10-02T19:57:03Z")
        )
        self.assertEqual(len(established["mrz_lifecycles"]), 1)
        self.assertEqual(
            next(
                item
                for item in established["episodes"]
                if item["hypothesis"] == "STR"
            )["state"],
            "STRUCTURE_ESTABLISHED",
        )

        future_cursor = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2027-01-01T00:00:00Z")
        )
        self.assertEqual(future_cursor["as_known_at"], "2026-11-12T00:00:00Z")

    def test_late_packet_is_hidden_until_received_but_keeps_event_time(self) -> None:
        inputs = nbis_inputs()
        late = observation(
            99,
            "nbis-late-str",
            Route.STR,
            "240.00",
            "2026-09-01T10:00:00Z",
            received_at="2026-10-01T10:00:00Z",
        )
        inputs["observations"] = (*inputs["observations"], late)
        before = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2026-09-30T23:59:59Z")
        )
        self.assertNotIn(
            "nbis-late-str",
            {item["canonical_event_id"] for item in before["observations"]},
        )
        after = build_symbol_opportunity(
            inputs, "NBIS", as_known_at=at("2026-10-01T10:00:00Z")
        )
        event = next(
            item
            for item in after["observations"]
            if item["canonical_event_id"] == "nbis-late-str"
        )
        self.assertEqual(event["effective_at"], "2026-09-01T10:00:00Z")
        self.assertEqual(event["known_at"], "2026-10-01T10:00:00Z")

    def test_group_aggregation_deduplicates_symbols_without_erasing_hypotheses(self) -> None:
        overview = build_opportunity_overview(nbis_inputs())
        self.assertEqual(overview["counts"]["candidate_symbols"], 1)
        self.assertEqual(len(overview["groups"]), 2)
        self.assertTrue(
            all(item["candidate_symbol_count"] == 1 for item in overview["groups"])
        )
        self.assertIn("multiple groups", overview["cross_group_note"])
        self.assertIn("not automatically upgraded", overview["detection_note"])


if __name__ == "__main__":
    unittest.main()
