from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.domain import (
    ActiveMRZ,
    ActivationSource,
    Observation,
    ObservationType,
    Route,
    StructuralLocation,
)
from app.group_evidence import (
    build_all_groups_evidence,
    build_named_group_evidence,
)
from app.peer_pressure import build_peer_pressure_report


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "group_evidence_historical.json")
    .read_text(encoding="utf-8")
)
AS_OF = datetime(2026, 11, 8, 8, tzinfo=timezone.utc)


def group(group_id: int, name: str, members: list[str]) -> dict:
    return {
        "id": group_id,
        "name": name,
        "members": members,
        "created_at": AS_OF - timedelta(days=30),
        "updated_at": AS_OF - timedelta(days=1),
    }


def endpoint(
    symbol: str,
    *,
    start_price: str = "50",
    current_price: str = "50",
    comparison_at: datetime,
    current_at: datetime,
) -> dict:
    return {
        "symbol": symbol,
        "comparison_event_id": f"{symbol}-then",
        "comparison_observation_price": Decimal(start_price),
        "comparison_ipda_20w_high": Decimal("100"),
        "comparison_ipda_20w_low": Decimal("0"),
        "comparison_observed_at": comparison_at,
        "current_event_id": f"{symbol}-now",
        "current_observation_price": Decimal(current_price),
        "current_ipda_20w_high": Decimal("100"),
        "current_ipda_20w_low": Decimal("0"),
        "current_observed_at": current_at,
    }


def active(symbol: str) -> ActiveMRZ:
    return ActiveMRZ(
        symbol=symbol,
        route_owner=Route.BTD,
        core_mrz_lower=Decimal("100"),
        core_mrz_upper=Decimal("101"),
        core_mrz_midpoint=Decimal("100.5"),
        structural_location=StructuralLocation.SHALLOW_DISCOUNT,
        confirming_observation_count=4,
        supporting_observation_count=4,
        activated_at=AS_OF - timedelta(days=10),
        activation_event_id=f"{symbol}-activation",
        formation_started_at=None,
        formation_completed_at=None,
        formation_duration_seconds=None,
        ipda_20w_high_at_activation=Decimal("120"),
        ipda_20w_low_at_activation=Decimal("80"),
        ipda_width_at_activation=Decimal("40"),
        normalized_span_at_activation=Decimal("0.01"),
        instrument_tick=Decimal("0.1"),
        activation_source=ActivationSource.PRODUCTION_QUALIFIED,
    )


def pressure_observations(symbol: str, direction: str) -> list[Observation]:
    price = Decimal("104") if direction == "higher" else Decimal("97")
    return [
        Observation(
            id=index,
            event_id=f"{symbol}-pressure-{index}",
            schema_version="4.3",
            symbol=symbol,
            route=Route.BTD,
            observation_type=ObservationType.RECLAIM,
            observation_price=price,
            observation_price_tick=Decimal("0.1"),
            ipda_20w_high=Decimal("120"),
            ipda_20w_low=Decimal("80"),
            observed_at=AS_OF - timedelta(hours=5 - index),
            received_at=AS_OF - timedelta(hours=5 - index),
        )
        for index in range(1, 5)
    ]


def inputs(
    window: str,
    groups: list[dict],
    *,
    endpoints: list[dict] | None = None,
    active_mrzs: list[ActiveMRZ] | None = None,
    observations: list[Observation] | None = None,
    migrations: list[dict] | None = None,
    pressure_events: list[dict] | None = None,
    location_observations: list[Observation] | None = None,
    near_miss_episodes: list[dict] | None = None,
) -> dict:
    duration = {"24H": timedelta(hours=24), "5D": timedelta(days=5), "20D": timedelta(days=20)}[window]
    return {
        "window": window,
        "as_of": AS_OF,
        "comparison_at": AS_OF - duration,
        "groups": groups,
        "endpoint_rows": endpoints or [],
        "active_mrzs": active_mrzs or [],
        "observations": observations or [],
        "migration_events": migrations or [],
        "pressure_events": pressure_events or [],
        "location_observations": location_observations or [],
        "near_miss_episodes": near_miss_episodes or [],
    }


def migration(symbol: str, index: int, direction: str) -> dict:
    return {
        "event_key": f"{symbol}:migration:{index}",
        "sequence": index,
        "symbol": symbol,
        "occurred_at": AS_OF - timedelta(hours=100 - index),
        "trigger_event_id": f"{symbol}-trigger-{index}",
        "previous_route_owner": "BTD",
        "route_owner": "STR" if index % 3 == 0 else "BTD",
        "old_core_mrz_lower": Decimal("99"),
        "old_core_mrz_upper": Decimal("101"),
        "new_core_mrz_lower": Decimal("109") if direction == "higher" else Decimal("89"),
        "new_core_mrz_upper": Decimal("111") if direction == "higher" else Decimal("91"),
        "new_core_mrz_midpoint": Decimal("110") if direction == "higher" else Decimal("90"),
        "structural_location": "shallow_premium_core_mrz" if direction == "higher" else "shallow_discount_core_mrz",
    }


def pressure_event(symbol: str, index: int, direction: str, occurred_at: datetime) -> dict:
    return {
        "id": index,
        "source_event_key": f"pressure:{symbol}:{index}",
        "symbol": symbol,
        "occurred_at": occurred_at,
        "lifecycle_activation_event_id": f"{symbol}-activation",
        "previous_pressure_state": "NEUTRAL",
        "current_pressure_state": "UP" if direction == "higher" else "DOWN",
        "route_owner": "BTD",
        "post_activation_observation_count": 4,
        "above_envelope_count": 0 if direction == "lower" else 4,
        "below_envelope_count": 4 if direction == "lower" else 0,
    }


class GroupEvidenceTests(unittest.TestCase):
    def test_24h_same_bucket_preserves_no_new_observation_semantics(self) -> None:
        fixture = FIXTURE["tracked_24h_no_new_observation"]
        members = [f"S{index:02d}" for index in range(51)]
        comparison_at = AS_OF - timedelta(hours=24)
        endpoints = [
            endpoint(
                symbol,
                comparison_at=comparison_at - timedelta(hours=1),
                current_at=(AS_OF - timedelta(hours=1)) if index < 5 else comparison_at - timedelta(hours=1),
            )
            for index, symbol in enumerate(members)
        ]
        payload = build_named_group_evidence(inputs("24H", [group(1, "Tracked", members)], endpoints=endpoints), group(1, "Tracked", members))
        self.assertEqual(payload["structural"]["summary"], {
            "moved_higher": fixture["structural"]["higher"],
            "moved_lower": fixture["structural"]["lower"],
            "same_bucket": fixture["structural"]["same_bucket"],
            "higher_steps": 0,
            "lower_steps": 0,
        })
        self.assertEqual(payload["coverage"]["structural_fresh_in_window"], 5)
        self.assertEqual(payload["coverage"]["structural_no_new_observation"], 46)
        self.assertNotIn("stable", json.dumps(payload).lower().split())

    def test_current_pressure_and_cumulative_events_remain_distinct(self) -> None:
        fixture = FIXTURE["crypto_24h_pressure_disagreement"]
        members = ["BTC", "ETH", "XRP", "WLDUSDT", "SOLUSDT", "DOGE", "ADA"]
        directional = members[:3]
        actives = [active(symbol) for symbol in directional]
        observations = [item for symbol in directional for item in pressure_observations(symbol, "higher")]
        endpoints = [endpoint(symbol, comparison_at=AS_OF - timedelta(days=2), current_at=AS_OF - timedelta(hours=1)) for symbol in members]
        events = [
            pressure_event("WLDUSDT", 1, "lower", AS_OF - timedelta(hours=2)),
            pressure_event("SOLUSDT", 2, "lower", AS_OF - timedelta(hours=3)),
        ]
        request = inputs("24H", [group(1, "Crypto", members)], endpoints=endpoints, active_mrzs=actives, observations=observations, pressure_events=events)
        payload = build_named_group_evidence(request, request["groups"][0])
        self.assertEqual(payload["directional"]["current_pressure"]["summary"], fixture["current_pressure"])
        cumulative = payload["directional"]["cumulative_lifecycle_pressure_events"]
        self.assertEqual(cumulative["summary"]["latest_event"], fixture["latest_cumulative_event"])
        self.assertEqual(cumulative["summary"]["latest_event_vs_current"], fixture["latest_event_vs_current"])
        self.assertTrue(all(event["comparison"] == "current_neutral" for event in cumulative["events"]))
        self.assertTrue(all(event["event_direction"] == "lower" for event in cumulative["events"]))

    def test_chinese_5d_preserves_cross_dimension_disagreement(self) -> None:
        fixture = FIXTURE["chinese_5d_dimension_disagreement"]
        members = [f"CN{index}" for index in range(9)]
        comparison_at = AS_OF - timedelta(days=5)
        endpoints = []
        for index, symbol in enumerate(members):
            start, current = (
                ("30", "50") if index < 3
                else ("10", "50") if index < 6
                else ("50", "50")
            )
            endpoints.append(endpoint(
                symbol,
                start_price=start,
                current_price=current,
                comparison_at=comparison_at,
                current_at=AS_OF - timedelta(hours=index + 1),
            ))
        actives = [active(symbol) for symbol in members[:5]]
        observations = [
            item
            for index, symbol in enumerate(members[:5])
            for item in pressure_observations(symbol, "higher" if index == 0 else "lower")
        ]
        request = inputs(
            "5D",
            [group(1, "Chinese", members)],
            endpoints=endpoints,
            active_mrzs=actives,
            observations=observations,
            migrations=[migration(members[0], 1, "lower")],
        )
        payload = build_named_group_evidence(request, request["groups"][0])
        structural = payload["structural"]["summary"]
        self.assertEqual(
            {key: structural[key] for key in ("moved_higher", "moved_lower", "same_bucket", "higher_steps")},
            {
                "moved_higher": fixture["structural"]["higher"],
                "moved_lower": fixture["structural"]["lower"],
                "same_bucket": fixture["structural"]["same_bucket"],
                "higher_steps": fixture["structural"]["higher_steps"],
            },
        )
        self.assertEqual(payload["coverage"]["structural_fresh_in_window"], fixture["fresh_in_window"])
        self.assertEqual(payload["directional"]["current_pressure"]["summary"], fixture["current_pressure"])
        self.assertEqual(
            payload["directional"]["cumulative_lifecycle_pressure_events"]["summary"]["latest_event"],
            fixture["latest_cumulative_event"],
        )
        migration_summary = payload["directional"]["mrz_migrations"]["summary"]
        self.assertEqual(migration_summary["unique_contributors"], fixture["migrations"]["unique_contributors"])
        self.assertEqual(migration_summary["event_count"], fixture["migrations"]["event_count"])
        self.assertEqual(payload["near_miss"]["active_episode_count"], 0)
        self.assertEqual(payload["ote"]["status"], "not_connected")
        self.assertIsNone(payload["ote"]["daily"])

    def test_repeat_migration_breadth_does_not_use_raw_event_count(self) -> None:
        fixture = FIXTURE["crypto_20d_repeat_migrations"]["migrations"]
        members = [f"C{index}" for index in range(7)]
        rows = []
        event_index = 1
        for symbol in members[:6]:
            for direction in (["higher"] * 2 + ["lower"] * 4):
                rows.append(migration(symbol, event_index, direction))
                event_index += 1
        for _ in range(8):
            rows.append(migration(members[6], event_index, "lower"))
            event_index += 1
        request = inputs("20D", [group(1, "Crypto", members)], migrations=rows)
        payload = build_named_group_evidence(request, request["groups"][0])
        summary = payload["directional"]["mrz_migrations"]["summary"]
        self.assertEqual(summary["unique_contributors"], fixture["unique_contributors"])
        self.assertEqual(summary["event_count"], fixture["event_count"])
        self.assertEqual(summary["higher_events"], fixture["higher"])
        self.assertEqual(summary["lower_events"], fixture["lower"])
        self.assertEqual(summary["repeated_contributors"], fixture["repeated_contributors"])
        self.assertEqual(summary["both_direction_contributors"], fixture["both_direction_contributors"])
        self.assertEqual(summary["unique_higher_contributors"], 6)
        self.assertEqual(summary["unique_lower_contributors"], 7)

    def test_near_miss_active_and_historical_episode_states_are_distinct(self) -> None:
        group_row = group(1, "Near Miss", ["A", "B"])
        rows = [
            {
                "id": 1,
                "episode_key": "near:A:1",
                "symbol": "A",
                "route_owner": "BTD",
                "started_at": AS_OF - timedelta(hours=8),
                "ended_at": None,
                "ended_reason": None,
                "canonical_candidate_event_id": "a-candidate",
                "canonical_structural_location": "shallow_discount_core_mrz",
                "canonical_shortfall_percentage_points": Decimal("0.2"),
                "canonical_supporting_observation_count": 4,
                "canonical_candidate_timestamp": AS_OF - timedelta(hours=8),
                "canonical_snapshot_reliable": True,
                "canonical_updated_at": AS_OF - timedelta(hours=1),
            },
            {
                "id": 2,
                "episode_key": "near:B:1",
                "symbol": "B",
                "route_owner": "STR",
                "started_at": AS_OF - timedelta(hours=12),
                "ended_at": AS_OF - timedelta(hours=3),
                "ended_reason": "NO_LONGER_CURRENT",
                "canonical_candidate_event_id": "b-candidate",
                "canonical_structural_location": "shallow_premium_core_mrz",
                "canonical_shortfall_percentage_points": Decimal("0.4"),
                "canonical_supporting_observation_count": 4,
                "canonical_candidate_timestamp": AS_OF - timedelta(hours=12),
                "canonical_snapshot_reliable": True,
                "canonical_updated_at": AS_OF - timedelta(hours=3),
            },
        ]
        request = inputs("24H", [group_row], near_miss_episodes=rows)
        payload = build_named_group_evidence(request, group_row)
        self.assertEqual(payload["near_miss"]["active_episode_count"], 1)
        self.assertEqual(payload["near_miss"]["historical_episode_count"], 1)
        self.assertEqual(payload["near_miss"]["active_symbols"], ["A"])
        members = {item["symbol"]: item for item in payload["members"]}
        self.assertTrue(members["A"]["near_miss"]["active"])
        self.assertFalse(members["B"]["near_miss"]["active"])

    def test_ote_not_connected_is_unavailable_not_zero(self) -> None:
        group_row = group(1, "OTE", ["A"])
        payload = build_named_group_evidence(inputs("24H", [group_row]), group_row)
        self.assertEqual(payload["ote"]["status"], "not_connected")
        self.assertEqual(payload["ote"]["source"], "EDGE_BOT")
        self.assertIsNone(payload["ote"]["daily"])
        self.assertIsNone(payload["ote"]["weekly"])
        self.assertIsNone(payload["members"][0]["ote"]["latest"])

    def test_equal_midpoint_route_migration_is_not_falsely_called_lower(self) -> None:
        row = migration("A", 1, "higher")
        row.update({
            "new_core_mrz_lower": Decimal("99"),
            "new_core_mrz_upper": Decimal("101"),
            "new_core_mrz_midpoint": Decimal("100"),
        })
        group_row = group(1, "Route-only", ["A"])
        payload = build_named_group_evidence(
            inputs("20D", [group_row], migrations=[row]),
            group_row,
        )
        migrations = payload["directional"]["mrz_migrations"]
        self.assertEqual(migrations["events"][0]["direction"], "same_midpoint")
        self.assertEqual(migrations["summary"]["same_midpoint_events"], 1)
        self.assertEqual(migrations["summary"]["lower_events"], 0)

    def test_crypto_20d_fixture_reconciles_every_stage_a_dimension(self) -> None:
        fixture = FIXTURE["crypto_20d_repeat_migrations"]
        members = [f"C{index}" for index in range(7)]
        comparison_at = AS_OF - timedelta(days=20)
        endpoints = []
        for index, symbol in enumerate(members):
            start, current = (
                ("90", "50") if index < 2
                else ("70", "50") if index < 4
                else ("50", "50")
            )
            endpoints.append(endpoint(
                symbol,
                start_price=start,
                current_price=current,
                comparison_at=comparison_at,
                current_at=AS_OF - timedelta(hours=index + 1),
            ))
        actives = [active(symbol) for symbol in members[:3]]
        observations = [
            item for symbol in members[:3] for item in pressure_observations(symbol, "higher")
        ]
        pressure_rows = [
            pressure_event(
                symbol,
                index + 1,
                "higher" if index < 4 else "lower",
                AS_OF - timedelta(hours=10 + index),
            )
            for index, symbol in enumerate(members)
        ]
        migration_rows = []
        event_index = 1
        for symbol in members[:6]:
            for direction in (["higher"] * 2 + ["lower"] * 4):
                migration_rows.append(migration(symbol, event_index, direction))
                event_index += 1
        for _ in range(8):
            migration_rows.append(migration(members[6], event_index, "lower"))
            event_index += 1
        request = inputs(
            "20D",
            [group(1, "Crypto", members)],
            endpoints=endpoints,
            active_mrzs=actives,
            observations=observations,
            migrations=migration_rows,
            pressure_events=pressure_rows,
        )
        payload = build_named_group_evidence(request, request["groups"][0])
        self.assertEqual(
            payload["structural"]["summary"],
            {
                "moved_higher": fixture["structural"]["higher"],
                "moved_lower": fixture["structural"]["lower"],
                "same_bucket": fixture["structural"]["same_bucket"],
                "higher_steps": 0,
                "lower_steps": fixture["structural"]["lower_steps"],
            },
        )
        self.assertEqual(payload["directional"]["current_pressure"]["summary"], fixture["current_pressure"])
        cumulative = payload["directional"]["cumulative_lifecycle_pressure_events"]["summary"]
        self.assertEqual(cumulative["latest_event"], fixture["latest_cumulative_event"])
        self.assertEqual(cumulative["latest_event_vs_current"], fixture["latest_event_vs_current"])
        migration_summary = payload["directional"]["mrz_migrations"]["summary"]
        for actual_key, fixture_key in (
            ("unique_contributors", "unique_contributors"),
            ("event_count", "event_count"),
            ("higher_events", "higher"),
            ("lower_events", "lower"),
            ("repeated_contributors", "repeated_contributors"),
            ("both_direction_contributors", "both_direction_contributors"),
        ):
            self.assertEqual(migration_summary[actual_key], fixture["migrations"][fixture_key])

    def test_current_pressure_is_shared_classifier_output_across_windows(self) -> None:
        members = ["A", "B"]
        group_row = group(1, "Parity", members)
        endpoints = [
            endpoint(
                symbol,
                comparison_at=AS_OF - timedelta(days=30),
                current_at=AS_OF - timedelta(hours=1),
            )
            for symbol in members
        ]
        actives = [active("A")]
        observations = pressure_observations("A", "higher")
        payloads = []
        for window in ("24H", "5D", "20D"):
            request = inputs(
                window,
                [group_row],
                endpoints=endpoints,
                active_mrzs=actives,
                observations=observations,
            )
            payloads.append(build_named_group_evidence(request, group_row))
        self.assertTrue(all(
            payload["directional"]["current_pressure"]["summary"]
            == payloads[0]["directional"]["current_pressure"]["summary"]
            for payload in payloads[1:]
        ))
        expected = build_peer_pressure_report(
            {
                "id": group_row["id"],
                "name": group_row["name"],
                "members": members,
                "current_state": {
                    "members": [
                        {
                            "symbol": symbol,
                            "current_location": "at_eqm",
                            "latest_observed_at": (AS_OF - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                        }
                        for symbol in members
                    ],
                },
            },
            actives,
            observations,
        )
        expected_by_symbol = {
            item["symbol"]: item
            for category in expected["categories"].values()
            for item in category
        }
        for payload in payloads:
            actual = payload["directional"]["current_pressure"]["members"]
            for item in actual:
                canonical = expected_by_symbol[item["symbol"]]
                self.assertEqual(item["direction"], canonical["direction"])
                self.assertEqual(item["evidence"], canonical["evidence"])

    def test_one_dimension_failure_retains_other_facts_without_false_zeroes(self) -> None:
        group_row = group(1, "Partial", ["A"])
        broken_migration = migration("A", 1, "higher")
        broken_migration["new_core_mrz_midpoint"] = "not-a-number"
        request = inputs(
            "5D",
            [group_row],
            endpoints=[endpoint(
                "A",
                comparison_at=AS_OF - timedelta(days=5),
                current_at=AS_OF - timedelta(hours=1),
            )],
            migrations=[broken_migration],
        )
        payload = build_named_group_evidence(request, group_row)
        self.assertEqual(payload["status"], "partial")
        self.assertEqual(payload["structural"]["status"], "available")
        self.assertEqual(payload["directional"]["current_pressure"]["status"], "available")
        self.assertEqual(payload["directional"]["mrz_migrations"], {
            "status": "unavailable",
            "reason": "migration_projection_failed",
        })

    def test_all_groups_deduplicates_canonical_events_across_contexts(self) -> None:
        fixture = FIXTURE["multi_group_duplicate_attribution"]
        unique = [f"M{index:02d}" for index in range(51)]
        groups = []
        cursor = 0
        for group_id in range(8):
            size = 7 if group_id < 3 else 6
            group_members = unique[cursor:cursor + size]
            cursor += size
            groups.append(group(group_id + 1, f"Group {group_id + 1}", group_members))
        for index, symbol in enumerate(unique[:6]):
            groups[(index + 1) % 8]["members"].append(symbol)
        rows = []
        for index in range(137):
            symbol = unique[index % 6] if index < 8 else unique[6 + (index % 45)]
            rows.append(migration(symbol, index + 1, "higher" if index % 2 else "lower"))
        payload = build_all_groups_evidence(inputs("20D", groups, migrations=rows))
        totals = payload["scope_totals"]
        self.assertEqual(totals["group_count"], fixture["group_count"])
        self.assertEqual(totals["member_slots"], fixture["member_slots"])
        self.assertEqual(totals["unique_members"], fixture["unique_members"])
        self.assertEqual(totals["canonical_migration_events"], fixture["canonical_events"])
        self.assertEqual(totals["group_context_migration_appearances"], fixture["group_context_appearances"])

    def test_window_aging_is_no_event_not_neutral_or_resolved(self) -> None:
        members = ["A"]
        old_event = pressure_event("A", 1, "higher", AS_OF - timedelta(days=2))
        five_day = inputs("5D", [group(1, "A", members)], pressure_events=[old_event])
        one_day = inputs("24H", [group(1, "A", members)], pressure_events=[])
        self.assertEqual(build_named_group_evidence(five_day, five_day["groups"][0])["directional"]["cumulative_lifecycle_pressure_events"]["summary"]["latest_event"]["higher"], 1)
        one_day_payload = build_named_group_evidence(one_day, one_day["groups"][0])
        self.assertEqual(one_day_payload["directional"]["cumulative_lifecycle_pressure_events"]["summary"]["latest_event"], {"higher": 0, "lower": 0, "none": 1})
        self.assertNotIn("resolved", json.dumps(one_day_payload).lower())

    def test_contract_has_no_stage_b_fields(self) -> None:
        request = inputs("24H", [group(1, "A", ["A"])])
        payload = build_all_groups_evidence(request)
        forbidden = {"condition", "attention_state", "score", "priority", "materiality", "resolved", "superseded"}

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertTrue(forbidden.isdisjoint(set(keys(payload))))


if __name__ == "__main__":
    unittest.main()
