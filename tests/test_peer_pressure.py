from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain import (
    ActivationSource,
    ActiveMRZ,
    Observation,
    ObservationType,
    Route,
    StructuralLocation,
)
from app.peer_pressure import build_peer_pressure_report, build_universe_pressure_report


BASE_TIME = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


def active(symbol: str, route: Route = Route.BTD) -> ActiveMRZ:
    return ActiveMRZ(
        symbol=symbol,
        route_owner=route,
        core_mrz_lower=Decimal("110"),
        core_mrz_upper=Decimal("111"),
        core_mrz_midpoint=Decimal("110.5"),
        structural_location=StructuralLocation.DEEP_DISCOUNT,
        confirming_observation_count=4,
        supporting_observation_count=4,
        activated_at=BASE_TIME,
        activation_event_id=f"{symbol}-activation",
        formation_started_at=BASE_TIME - timedelta(minutes=3),
        formation_completed_at=BASE_TIME,
        formation_duration_seconds=Decimal("180"),
        ipda_20w_high_at_activation=Decimal("200"),
        ipda_20w_low_at_activation=Decimal("100"),
        ipda_width_at_activation=Decimal("100"),
        normalized_span_at_activation=Decimal("0.01"),
        instrument_tick=Decimal("0.01"),
        activation_source=ActivationSource.PRODUCTION_QUALIFIED,
    )


def observation(symbol: str, index: int, price: str, route: Route = Route.BTD) -> Observation:
    observed_at = BASE_TIME + timedelta(minutes=index)
    return Observation(
        id=index,
        event_id=f"{symbol}-{index}",
        schema_version="4.3",
        symbol=symbol,
        route=route,
        observation_type=(
            ObservationType.RECLAIM if route is Route.BTD else ObservationType.REJECTION
        ),
        observation_price=Decimal(price),
        observation_price_tick=Decimal("0.01"),
        ipda_20w_high=Decimal("200"),
        ipda_20w_low=Decimal("100"),
        observed_at=observed_at,
        received_at=observed_at,
    )


def group(*members: str) -> dict[str, object]:
    return {
        "id": 7,
        "name": "Peers",
        "members": list(members),
        "current_state": {
            "members": [
                {
                    "symbol": symbol,
                    "current_location": (
                        "deep_premium" if index % 2 else "deep_discount"
                    ),
                    "latest_observed_at": "2026-09-20T12:10:00Z",
                    "has_active_mrz": True,
                    "route_owner": "BTD",
                }
                for index, symbol in enumerate(members)
            ]
        },
    }


def symbol_state(symbol: str, location: str | None) -> dict[str, object]:
    return {
        "symbol": symbol,
        "current_price_location": location,
        "latest_observed_at": "2026-09-20T12:10:00Z",
    }


class PeerPressureTests(unittest.TestCase):
    def test_directional_counts_participation_and_drilldown_reconcile(self) -> None:
        report = build_peer_pressure_report(
            group("UP", "DOWN", "QUIET", "MISSING"),
            (
                active("UP", Route.STR),
                active("DOWN", Route.BTD),
                active("QUIET", Route.STR),
            ),
            (
                observation("UP", 1, "114", Route.STR),
                observation("UP", 2, "115", Route.STR),
                observation("UP", 3, "116", Route.STR),
                observation("DOWN", 4, "107"),
                observation("DOWN", 5, "106"),
                observation("DOWN", 6, "105"),
                observation("QUIET", 7, "111", Route.STR),
            ),
        )

        self.assertEqual(report["counts"], {"higher": 1, "lower": 1, "neutral": 2})
        self.assertEqual(report["participation"], {"count": 2, "total": 4})
        self.assertEqual(report["headline"]["label"], "Mixed / Balanced")
        self.assertEqual(
            {
                direction: [member["symbol"] for member in members]
                for direction, members in report["categories"].items()
            },
            {
                "higher": ["UP"],
                "lower": ["DOWN"],
                "neutral": ["QUIET", "MISSING"],
            },
        )
        self.assertEqual(sum(report["counts"].values()), report["member_count"])

    def test_location_and_route_alone_never_create_pressure(self) -> None:
        report = build_peer_pressure_report(
            group("BTD", "STR", "NOACTIVE"),
            (active("BTD", Route.BTD), active("STR", Route.STR)),
            (),
        )

        self.assertEqual(report["counts"], {"higher": 0, "lower": 0, "neutral": 3})
        self.assertEqual(report["participation"], {"count": 0, "total": 3})
        self.assertEqual(report["headline"]["label"], "Insufficient Participation")
        self.assertEqual(
            report["categories"]["neutral"][2]["evidence"]["status"],
            "NO_ACTIVE_MRZ",
        )

    def test_member_can_change_higher_to_neutral_to_lower_deterministically(self) -> None:
        cohort = group("A")
        authority = (active("A"),)
        higher = (
            observation("A", 1, "114"),
            observation("A", 2, "115"),
            observation("A", 3, "116"),
        )
        neutral = (
            *higher,
            observation("A", 4, "107"),
            observation("A", 5, "106"),
        )
        lower = (
            *neutral,
            observation("A", 6, "105"),
        )

        self.assertEqual(build_peer_pressure_report(cohort, authority, higher)["counts"]["higher"], 1)
        self.assertEqual(build_peer_pressure_report(cohort, authority, neutral)["counts"]["neutral"], 1)
        first = build_peer_pressure_report(cohort, authority, lower)
        second = build_peer_pressure_report(cohort, authority, tuple(reversed(lower)))
        self.assertEqual(first["counts"]["lower"], 1)
        self.assertEqual(first, second)

    def test_unanimous_and_membership_changes_update_counts(self) -> None:
        authorities = (active("A"), active("B"))
        evidence = (
            observation("A", 1, "114"),
            observation("A", 2, "115"),
            observation("A", 3, "116"),
            observation("B", 4, "114"),
            observation("B", 5, "115"),
            observation("B", 6, "116"),
        )
        unanimous = build_peer_pressure_report(group("A", "B"), authorities, evidence)
        removed = build_peer_pressure_report(group("B"), authorities, evidence)
        added = build_peer_pressure_report(group("A", "B", "NEW"), authorities, evidence)

        self.assertEqual(unanimous["counts"], {"higher": 2, "lower": 0, "neutral": 0})
        self.assertEqual(unanimous["headline"]["label"], "Upward Pressure")
        self.assertEqual(removed["counts"], {"higher": 1, "lower": 0, "neutral": 0})
        self.assertEqual(added["counts"], {"higher": 2, "lower": 0, "neutral": 1})
        self.assertEqual(added["participation"], {"count": 2, "total": 3})

    def test_eth_regression_uses_current_regime_not_cumulative_majority(self) -> None:
        sequence = "UDDDDDDDDUUUU"
        prices = {"U": "114", "D": "107"}
        evidence = tuple(
            observation("ETHUSDT", index, prices[direction])
            for index, direction in enumerate(sequence, 1)
        )

        report = build_peer_pressure_report(
            group("ETHUSDT"),
            (active("ETHUSDT"),),
            tuple(reversed(evidence)),
        )
        member = report["categories"]["higher"][0]

        self.assertEqual(report["counts"], {"higher": 1, "lower": 0, "neutral": 0})
        self.assertEqual(member["evidence"]["higher_observation_count"], 5)
        self.assertEqual(member["evidence"]["lower_observation_count"], 8)
        self.assertEqual(
            [item["direction"] for item in member["evidence"]["recent_sequence"]],
            ["UP", "UP", "UP", "UP"],
        )
        self.assertEqual(
            member["evidence"]["current_pressure_since"],
            "2026-09-20T12:12:00Z",
        )
        self.assertEqual(
            member["evidence"]["latest_pressure_observed_at"],
            "2026-09-20T12:13:00Z",
        )

    def test_universe_breadth_and_location_matrix_reconcile_exactly(self) -> None:
        states = (
            symbol_state("UP", "deep_discount"),
            symbol_state("QUIET", "deep_discount"),
            symbol_state("DOWN", "shallow_premium"),
            symbol_state("NOACTIVE", "deep_premium"),
            symbol_state("EQM", "at_eqm"),
            symbol_state("OUTSIDE", "above_ipda_range"),
        )
        authorities = (active("UP"), active("QUIET"), active("DOWN"))
        evidence = (
            observation("UP", 1, "114"),
            observation("UP", 2, "115"),
            observation("UP", 3, "116"),
            observation("DOWN", 4, "107"),
            observation("DOWN", 5, "106"),
            observation("DOWN", 6, "105"),
        )

        report = build_universe_pressure_report(states, authorities, evidence)

        self.assertEqual(report["counts"], {"higher": 1, "lower": 1, "neutral": 3})
        self.assertEqual(report["participation"], {"count": 2, "total": 5})
        self.assertEqual(report["excluded_unclassified_count"], 1)
        rows = report["pressure_map"]["locations"]
        self.assertEqual(
            rows["deep_discount"],
            {
                "counts": {"higher": 1, "lower": 0, "neutral": 1},
                "participation": {"count": 1, "total": 2},
            },
        )
        self.assertEqual(
            rows["shallow_premium"]["counts"],
            {"higher": 0, "lower": 1, "neutral": 0},
        )
        self.assertEqual(
            rows["at_eqm"]["counts"],
            {"higher": 0, "lower": 0, "neutral": 1},
            "pressure remains independently derived for an exact-EQM member",
        )
        self.assertEqual(report["pressure_map"]["totals"], report["counts"])
        self.assertEqual(
            sum(row["participation"]["total"] for row in rows.values()),
            report["member_count"],
        )

    def test_universe_and_group_are_scopes_over_identical_symbol_pressure(self) -> None:
        states = (
            symbol_state("UP", "deep_discount"),
            symbol_state("DOWN", "shallow_premium"),
            symbol_state("NOACTIVE", "deep_premium"),
        )
        cohort = {
            "id": 9,
            "name": "Same state",
            "members": [state["symbol"] for state in states],
            "current_state": {
                "members": [
                    {
                        "symbol": state["symbol"],
                        "current_location": state["current_price_location"],
                        "latest_observed_at": state["latest_observed_at"],
                    }
                    for state in states
                ]
            },
        }
        authorities = (active("UP"), active("DOWN"))
        evidence = (
            observation("UP", 1, "114"),
            observation("UP", 2, "115"),
            observation("UP", 3, "116"),
            observation("DOWN", 4, "107"),
            observation("DOWN", 5, "106"),
            observation("DOWN", 6, "105"),
        )

        universe = build_universe_pressure_report(states, authorities, evidence)
        peers = build_peer_pressure_report(cohort, authorities, evidence)
        universe_by_symbol = {
            item["symbol"]: item
            for members in universe["categories"].values()
            for item in members
        }
        peer_by_symbol = {
            item["symbol"]: item
            for members in peers["categories"].values()
            for item in members
        }

        self.assertEqual(universe_by_symbol, peer_by_symbol)
        self.assertEqual(universe["counts"], peers["counts"])
        self.assertEqual(universe["headline"], peers["headline"])

    def test_universe_with_no_participants_is_all_neutral(self) -> None:
        report = build_universe_pressure_report(
            (
                symbol_state("NEW", "deep_discount"),
                symbol_state("QUIET", "deep_premium"),
            ),
            (active("QUIET"),),
            (),
        )

        self.assertEqual(report["counts"], {"higher": 0, "lower": 0, "neutral": 2})
        self.assertEqual(report["participation"], {"count": 0, "total": 2})
        self.assertEqual(report["headline"]["label"], "Insufficient Participation")


if __name__ == "__main__":
    unittest.main()
