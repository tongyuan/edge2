from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain import ActiveMRZ, Observation
from app.peer_pressure import build_peer_pressure_report
from app.structure import classify_ipda_location


CONTRACT_VERSION = "group-activity-1"
LOCATION_KEYS = (
    "deep_discount",
    "shallow_discount",
    "at_eqm",
    "shallow_premium",
    "deep_premium",
)
LOCATION_LABELS = {
    "deep_discount": "Deep Discount",
    "shallow_discount": "Shallow Discount",
    "at_eqm": "Equilibrium",
    "shallow_premium": "Shallow Premium",
    "deep_premium": "Deep Premium",
}
PRESSURE_ORDER = {"higher": 0, "lower": 1, "neutral": 2}
LIMITATIONS = [
    "Historical evidence is attributed to membership at the response snapshot.",
    "Current pressure is a present snapshot, not a windowed historical series.",
    "No event from an event-driven tracker is not proof that its source was freshly evaluated.",
    "OTE activity is unavailable until the supported EDGE_BOT feed is connected.",
]
OTE_NOT_CONNECTED = {
    "status": "not_connected",
    "message": "OTE feed not connected",
    "source": "EDGE_BOT",
    "daily": None,
    "weekly": None,
    "latest": None,
}


def _iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _decimal_text(value: Any) -> str | None:
    return format(Decimal(value), "f") if value is not None else None


def _location(row: Mapping[str, Any] | None, prefix: str) -> str | None:
    if not row:
        return None
    price = row.get(f"{prefix}_observation_price")
    high = row.get(f"{prefix}_ipda_20w_high")
    low = row.get(f"{prefix}_ipda_20w_low")
    if price is None or high is None or low is None:
        return None
    classified = classify_ipda_location(Decimal(price), Decimal(high), Decimal(low))
    return classified.value if classified and classified.value in LOCATION_KEYS else None


def _observation_location(observation: Observation) -> str | None:
    classified = classify_ipda_location(
        observation.observation_price,
        observation.ipda_20w_high,
        observation.ipda_20w_low,
    )
    return classified.value if classified and classified.value in LOCATION_KEYS else None


def _distribution_point(
    at: datetime,
    members: Sequence[str],
    locations: Mapping[str, str | None],
    source_observation_ids: Sequence[str] = (),
) -> dict[str, Any]:
    buckets = {key: 0 for key in LOCATION_KEYS}
    for symbol in members:
        location = locations.get(symbol)
        if location in buckets:
            buckets[location] += 1
    eligible = sum(buckets.values())
    return {
        "at": _iso(at),
        "buckets": buckets,
        "aggregate": {
            "lower": buckets["deep_discount"] + buckets["shallow_discount"],
            "neutral": buckets["at_eqm"],
            "higher": buckets["shallow_premium"] + buckets["deep_premium"],
            "eligible": eligible,
            "unavailable": len(members) - eligible,
        },
        "source_observation_ids": list(source_observation_ids),
    }


def _location_history(
    members: Sequence[str],
    endpoint_by_symbol: Mapping[str, Mapping[str, Any]],
    observations: Sequence[Observation],
    comparison_at: datetime,
    as_of: datetime,
) -> dict[str, Any]:
    member_set = set(members)
    locations = {
        symbol: _location(endpoint_by_symbol.get(symbol), "comparison")
        for symbol in members
    }
    points = [_distribution_point(comparison_at, members, locations)]
    grouped: dict[datetime, list[Observation]] = defaultdict(list)
    for observation in observations:
        if observation.symbol in member_set and comparison_at < observation.observed_at <= as_of:
            grouped[observation.observed_at].append(observation)
    for observed_at in sorted(grouped):
        source_ids: list[str] = []
        for observation in grouped[observed_at]:
            locations[observation.symbol] = _observation_location(observation)
            source_ids.append(observation.event_id)
        points.append(_distribution_point(observed_at, members, locations, source_ids))
    for symbol in members:
        current = _location(endpoint_by_symbol.get(symbol), "current")
        if current is not None:
            locations[symbol] = current
    if points[-1]["at"] != _iso(as_of):
        points.append(_distribution_point(as_of, members, locations))
    if len(points) > 60:
        keep = {0, len(points) - 1}
        stride = (len(points) - 1) / 58
        keep.update(round(index * stride) for index in range(1, 59))
        points = [point for index, point in enumerate(points) if index in keep]
    if not any(point["aggregate"]["eligible"] for point in points):
        return {
            "status": "unavailable",
            "reason": "insufficient_historical_location_data",
            "message": "Historical location data unavailable for current members.",
        }
    first = points[0]
    current = points[-1]
    same_coverage = (
        first["aggregate"]["eligible"] > 0
        and first["aggregate"]["eligible"] == current["aggregate"]["eligible"]
    )
    distribution_summary = []
    for key in reversed(LOCATION_KEYS):
        first_count = int(first["buckets"][key])
        current_count = int(current["buckets"][key])
        first_eligible = int(first["aggregate"]["eligible"])
        current_eligible = int(current["aggregate"]["eligible"])
        first_percent = (
            (first_count / first_eligible) * 100 if first_eligible else None
        )
        current_percent = (
            (current_count / current_eligible) * 100 if current_eligible else None
        )
        distribution_summary.append({
            "key": key,
            "label": LOCATION_LABELS[key],
            "current_count": current_count,
            "current_eligible": current_eligible,
            "current_percent": current_percent,
            "start_count": first_count,
            "start_eligible": first_eligible,
            "start_percent": first_percent,
            "count_change": current_count - first_count if same_coverage else None,
            "percentage_point_change": (
                current_percent - first_percent
                if same_coverage
                and current_percent is not None
                and first_percent is not None
                else None
            ),
            "change_status": "comparable" if same_coverage else "coverage_changed",
        })
    return {
        "status": "available",
        "method": "last_known_canonical_observation_reconstruction",
        "points": points,
        "current_distribution_summary": distribution_summary,
        "comparison_basis": {
            "membership": "current_saved_group_membership",
            "same_eligible_coverage": same_coverage,
            "start_eligible": first["aggregate"]["eligible"],
            "current_eligible": current["aggregate"]["eligible"],
            "message": (
                "Change compares the same current group members with complete "
                "location coverage at both endpoints."
                if same_coverage
                else "Change is unavailable because eligible location coverage "
                "differs between interval endpoints."
            ),
        },
        "canonical_buckets": [
            {"key": key, "label": LOCATION_LABELS[key]} for key in LOCATION_KEYS
        ],
    }


def _location_activity(
    members: Sequence[str],
    endpoint_by_symbol: Mapping[str, Mapping[str, Any]],
    observations: Sequence[Observation],
    comparison_at: datetime,
    as_of: datetime,
) -> dict[str, Any]:
    """Return recorded bucket transitions and conservative comparison coverage."""
    rank = {key: index for index, key in enumerate(LOCATION_KEYS)}
    member_set = set(members)
    by_symbol: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        if (
            observation.symbol in member_set
            and comparison_at < observation.observed_at <= as_of
        ):
            by_symbol[observation.symbol].append(observation)
    for symbol_observations in by_symbol.values():
        symbol_observations.sort(
            key=lambda item: (item.observed_at, item.received_at, item.id)
        )

    records: list[dict[str, Any]] = []
    coverage_members: list[dict[str, Any]] = []
    comparable_members = fresh_comparable_members = 0
    for symbol in members:
        endpoint = endpoint_by_symbol.get(symbol)
        previous = _location(endpoint, "comparison")
        if previous is None:
            coverage_members.append({
                "symbol": symbol,
                "status": "insufficient_data",
                "reason": "comparison_location_unavailable",
            })
            continue
        comparable_members += 1
        valid_observations = [
            (observation, _observation_location(observation))
            for observation in by_symbol.get(symbol, ())
        ]
        valid_observations = [
            (observation, location)
            for observation, location in valid_observations
            if location is not None
        ]
        if not valid_observations:
            coverage_members.append({
                "symbol": symbol,
                "status": "insufficient_data",
                "reason": "no_comparable_observation_in_window",
                "comparison_location": previous,
                "comparison_observed_at": _iso(
                    endpoint.get("comparison_observed_at") if endpoint else None
                ),
            })
            continue
        fresh_comparable_members += 1
        symbol_change_count = 0
        for observation, current in valid_observations:
            if current != previous:
                direction = "higher" if rank[current] > rank[previous] else "lower"
                records.append({
                    "id": f"ipda:{observation.event_id}",
                    "tracker": "ipda",
                    "event_type": "IPDA_LOCATION_CHANGED",
                    "symbol": symbol,
                    "occurred_at": _iso(observation.observed_at),
                    "recorded_at": _iso(observation.received_at),
                    "direction": direction,
                    "previous_location": previous,
                    "previous_location_label": LOCATION_LABELS[previous],
                    "new_location": current,
                    "new_location_label": LOCATION_LABELS[current],
                    "magnitude_steps": abs(rank[current] - rank[previous]),
                    "source_event_id": observation.event_id,
                    "timestamp_semantics": "canonical_observation_timestamp",
                })
                symbol_change_count += 1
            previous = current
        coverage_members.append({
            "symbol": symbol,
            "status": "changed" if symbol_change_count else "no_change",
            "comparison_location": _location(endpoint, "comparison"),
            "comparison_observed_at": _iso(
                endpoint.get("comparison_observed_at") if endpoint else None
            ),
            "fresh_observation_count": len(valid_observations),
            "latest_observed_at": _iso(valid_observations[-1][0].observed_at),
            "transition_count": symbol_change_count,
        })
    records.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    return {
        "status": "available",
        "records": records,
        "coverage": {
            "member_total": len(members),
            "comparison_available": comparable_members,
            "fresh_comparable": fresh_comparable_members,
            "insufficient": len(members) - fresh_comparable_members,
            "members": coverage_members,
        },
    }


def _near_misses(
    members: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    comparison_at: datetime,
    as_of: datetime,
) -> dict[str, Any]:
    member_set = set(members)
    episodes = []
    for row in rows:
        symbol = str(row["symbol"])
        if symbol not in member_set:
            continue
        started_at = row["started_at"]
        ended_at = row.get("ended_at")
        active = ended_at is None or ended_at > as_of
        episodes.append({
            "id": int(row["id"]),
            "episode_key": str(row["episode_key"]),
            "symbol": symbol,
            "route_owner": str(row["route_owner"]),
            "started_at": _iso(started_at),
            "ended_at": _iso(ended_at),
            "ended_reason": row.get("ended_reason"),
            "active": active,
            "started_in_window": started_at > comparison_at,
            "candidate_event_id": row.get("canonical_candidate_event_id"),
            "candidate_location": row.get("canonical_structural_location"),
            "shortfall_percentage_points": _decimal_text(
                row.get("canonical_shortfall_percentage_points")
            ),
            "supporting_observation_count": row.get(
                "canonical_supporting_observation_count"
            ),
            "candidate_timestamp": _iso(row.get("canonical_candidate_timestamp")),
            "snapshot_reliable": bool(row.get("canonical_snapshot_reliable")),
            "updated_at": _iso(row.get("canonical_updated_at")),
        })
    episodes.sort(key=lambda item: (item["started_at"], item["id"]), reverse=True)
    active_symbols = sorted({item["symbol"] for item in episodes if item["active"]})
    historical = [item for item in episodes if not item["active"]]
    return {
        "status": "available",
        "active_episode_count": sum(item["active"] for item in episodes),
        "active_symbol_count": len(active_symbols),
        "active_symbols": active_symbols,
        "historical_episode_count": len(historical),
        "episodes": episodes,
    }


def _snapshot(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "key": str(inputs["window"]),
        "semantics": "elapsed_calendar_time",
        "as_of": _iso(inputs["as_of"]),
        "comparison_at": _iso(inputs["comparison_at"]),
    }


def _structural(
    members: Sequence[str],
    endpoint_by_symbol: Mapping[str, Mapping[str, Any]],
    comparison_at: datetime,
) -> tuple[dict[str, Any], dict[str, int], list[datetime]]:
    rank = {key: index for index, key in enumerate(LOCATION_KEYS)}
    distribution = {key: 0 for key in LOCATION_KEYS}
    distribution["unavailable"] = 0
    contributors: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    current_available = comparable = fresh = no_new = 0
    higher = lower = same = higher_steps = lower_steps = 0
    evidence_times: list[datetime] = []

    for symbol in members:
        row = endpoint_by_symbol.get(symbol)
        current_location = _location(row, "current")
        start_location = _location(row, "comparison")
        if current_location is None:
            distribution["unavailable"] += 1
            unavailable.append({"symbol": symbol, "reason": "current_location_unavailable"})
            continue
        current_available += 1
        distribution[current_location] += 1
        current_observed_at = row.get("current_observed_at") if row else None
        if current_observed_at is not None:
            evidence_times.append(current_observed_at)
        if start_location is None:
            unavailable.append({
                "symbol": symbol,
                "reason": "comparison_location_unavailable",
                "current_location": current_location,
                "current_observed_at": _iso(current_observed_at),
            })
            continue

        comparable += 1
        magnitude = abs(rank[current_location] - rank[start_location])
        if rank[current_location] > rank[start_location]:
            direction = "higher"
            higher += 1
            higher_steps += magnitude
        elif rank[current_location] < rank[start_location]:
            direction = "lower"
            lower += 1
            lower_steps += magnitude
        else:
            direction = "same_bucket"
            same += 1
        new_observation = bool(
            current_observed_at is not None and current_observed_at > comparison_at
        )
        fresh += int(new_observation)
        no_new += int(not new_observation)
        source_ids = []
        for key in ("comparison_event_id", "current_event_id"):
            source_id = row.get(key) if row else None
            if source_id and source_id not in source_ids:
                source_ids.append(str(source_id))
        contributors.append({
            "symbol": symbol,
            "start_location": start_location,
            "start_location_label": LOCATION_LABELS[start_location],
            "current_location": current_location,
            "current_location_label": LOCATION_LABELS[current_location],
            "direction": direction,
            "magnitude_steps": magnitude,
            "comparison_observed_at": _iso(row.get("comparison_observed_at")),
            "current_observed_at": _iso(current_observed_at),
            "new_observation_in_window": new_observation,
            "source_observation_ids": source_ids,
        })

    contributors.sort(key=lambda item: item["symbol"])
    unavailable.sort(key=lambda item: item["symbol"])
    if higher + lower + same != comparable:
        raise ValueError("structural contributors do not reconcile")
    if fresh + no_new != comparable:
        raise ValueError("structural freshness does not reconcile")
    summary = {
        "moved_higher": higher,
        "moved_lower": lower,
        "same_bucket": same,
        "higher_steps": higher_steps,
        "lower_steps": lower_steps,
    }
    coverage = {
        "structural_current_available": current_available,
        "structural_comparable": comparable,
        "structural_fresh_in_window": fresh,
        "structural_no_new_observation": no_new,
        "structural_unavailable_current": len(members) - current_available,
    }
    return ({
        "status": "available",
        "summary": summary,
        "current_distribution": distribution,
        "contributors": contributors,
        "unavailable_members": unavailable,
        "endpoint_observed_at": {
            "earliest_current": _iso(min(evidence_times)) if evidence_times else None,
            "latest_current": _iso(max(evidence_times)) if evidence_times else None,
        },
        "limitation": "Endpoint comparison is not a stability claim.",
    }, coverage, evidence_times)


def _current_pressure(
    group: Mapping[str, Any],
    members: Sequence[str],
    endpoint_by_symbol: Mapping[str, Mapping[str, Any]],
    active_mrzs: Sequence[ActiveMRZ],
    observations: Sequence[Observation],
    comparison_at: datetime,
) -> tuple[dict[str, Any], dict[str, int], dict[str, dict[str, Any]], list[datetime]]:
    member_states = []
    for symbol in members:
        row = endpoint_by_symbol.get(symbol, {})
        member_states.append({
            "symbol": symbol,
            "current_location": _location(row, "current"),
            "latest_observed_at": _iso(row.get("current_observed_at")),
        })
    group_report = {
        "id": group["id"],
        "name": group["name"],
        "members": list(members),
        "current_state": {"members": member_states},
    }
    report = build_peer_pressure_report(group_report, active_mrzs, observations)
    active_by_symbol = {active.symbol: active for active in active_mrzs}
    flattened: list[dict[str, Any]] = []
    by_symbol: dict[str, dict[str, Any]] = {}
    evidence_times: list[datetime] = []
    fresh_directional = 0
    for direction in ("higher", "lower", "neutral"):
        for raw in report["categories"][direction]:
            item = dict(raw)
            active = active_by_symbol.get(item["symbol"])
            item["current_pressure_label"] = "Current pressure"
            item["lifecycle_activation_event_id"] = (
                active.activation_event_id if active else None
            )
            if active:
                item["active_mrz"] = {
                    **item["active_mrz"],
                    "activation_event_id": active.activation_event_id,
                    "activation_source": active.activation_source.value,
                    "authority": {
                        "lower": _decimal_text(active.core_mrz_lower),
                        "upper": _decimal_text(active.core_mrz_upper),
                        "midpoint": _decimal_text(active.core_mrz_midpoint),
                    },
                }
            evidence_at = item.get("evidence", {}).get("latest_pressure_observed_at")
            evidence_datetime = next(
                (
                    observation.observed_at
                    for observation in reversed(observations)
                    if observation.symbol == item["symbol"]
                    and _iso(observation.observed_at) == evidence_at
                ),
                None,
            )
            item["evidence_in_window"] = bool(
                direction != "neutral"
                and evidence_datetime is not None
                and evidence_datetime > comparison_at
            )
            fresh_directional += int(item["evidence_in_window"])
            if evidence_datetime is not None:
                evidence_times.append(evidence_datetime)
            flattened.append(item)
            by_symbol[item["symbol"]] = item
    flattened.sort(key=lambda item: (PRESSURE_ORDER[item["direction"]], item["symbol"]))
    counts = dict(report["counts"])
    active_count = sum(1 for symbol in members if symbol in active_by_symbol)
    directional = counts["higher"] + counts["lower"]
    coverage = {
        "current_pressure_evaluated": len(flattened),
        "current_pressure_active_mrz": active_count,
        "current_pressure_directional": directional,
        "current_pressure_evidence_fresh_in_window": fresh_directional,
    }
    return ({
        "status": "available",
        "summary": counts,
        "members": flattened,
        "snapshot_semantics": "present_at_as_of",
    }, coverage, by_symbol, evidence_times)


def _pressure_events(
    members: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    current_by_symbol: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[datetime]]:
    member_set = set(members)
    events: list[dict[str, Any]] = []
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    lifecycle_directions: dict[tuple[str, str], set[str]] = defaultdict(set)
    evidence_times: list[datetime] = []
    for row in rows:
        symbol = str(row["symbol"])
        if symbol not in member_set:
            continue
        event_direction = "higher" if str(row["current_pressure_state"]) == "UP" else "lower"
        current = current_by_symbol.get(symbol)
        current_direction = current.get("direction") if current else None
        if current_direction is None:
            comparison = "current_unavailable"
        elif current_direction == "neutral":
            comparison = "current_neutral"
        elif current_direction == event_direction:
            comparison = "same_direction"
        else:
            comparison = "opposite_direction"
        occurred_at = row["occurred_at"]
        evidence_times.append(occurred_at)
        event = {
            "id": int(row["id"]),
            "source_event_key": str(row["source_event_key"]),
            "event_id": str(row["source_event_key"]),
            "symbol": symbol,
            "lifecycle_activation_event_id": str(row["lifecycle_activation_event_id"]),
            "previous_state": str(row["previous_pressure_state"]),
            "event_direction": event_direction,
            "occurred_at": _iso(occurred_at),
            "evaluated_at": _iso(occurred_at),
            "route_owner": str(row["route_owner"]),
            "post_activation_observation_count": int(row["post_activation_observation_count"]),
            "above_envelope_count": int(row["above_envelope_count"]),
            "below_envelope_count": int(row["below_envelope_count"]),
            "current_pressure_direction": current_direction,
            "current_pressure_evidence_at": (
                current.get("evidence", {}).get("latest_pressure_observed_at")
                if current else None
            ),
            "comparison": comparison,
        }
        events.append(event)
        by_symbol[symbol].append(event)
        lifecycle_directions[(symbol, event["lifecycle_activation_event_id"])].add(event_direction)
    events.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    latest_by_member = []
    latest_counts = {"higher": 0, "lower": 0, "none": 0}
    comparison_counts = {
        "same_direction": 0,
        "current_neutral": 0,
        "opposite_direction": 0,
        "current_unavailable": 0,
    }
    for symbol in members:
        latest = sorted(
            by_symbol.get(symbol, ()),
            key=lambda item: (item["occurred_at"], item["id"]),
            reverse=True,
        )
        if not latest:
            latest_by_member.append({"symbol": symbol, "event_direction": None, "state": "none"})
            latest_counts["none"] += 1
            continue
        event = latest[0]
        latest_by_member.append({
            "symbol": symbol,
            "event_direction": event["event_direction"],
            "state": event["event_direction"],
            "event_id": event["event_id"],
            "occurred_at": event["occurred_at"],
            "comparison": event["comparison"],
        })
        latest_counts[event["event_direction"]] += 1
        comparison_counts[event["comparison"]] += 1
    if sum(latest_counts.values()) != len(members):
        raise ValueError("latest cumulative events do not reconcile")
    summary = {
        "unique_contributors": len(by_symbol),
        "event_count": len(events),
        "higher_events": sum(event["event_direction"] == "higher" for event in events),
        "lower_events": sum(event["event_direction"] == "lower" for event in events),
        "repeated_contributors": sum(len(items) > 1 for items in by_symbol.values()),
        "both_direction_contributors": len({
            symbol for (symbol, _lifecycle), directions in lifecycle_directions.items()
            if len(directions) > 1
        }),
        "latest_event": latest_counts,
        "latest_event_vs_current": comparison_counts,
    }
    return ({
        "status": "available",
        "summary": summary,
        "latest_by_member": latest_by_member,
        "events": events,
    }, evidence_times)


def _migration_direction(row: Mapping[str, Any]) -> str:
    old_midpoint = (
        Decimal(row["old_core_mrz_lower"]) + Decimal(row["old_core_mrz_upper"])
    ) / Decimal("2")
    new_midpoint = Decimal(row["new_core_mrz_midpoint"])
    if new_midpoint > old_midpoint:
        return "higher"
    if new_midpoint < old_midpoint:
        return "lower"
    return "same_midpoint"


def _migrations(
    members: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[datetime]]:
    member_set = set(members)
    selected = [row for row in rows if str(row["symbol"]) in member_set]
    ascending = sorted(
        selected,
        key=lambda row: (row["occurred_at"], int(row["sequence"]), str(row["event_key"])),
    )
    repeat_index: dict[str, int] = defaultdict(int)
    events = []
    evidence_times = []
    for row in ascending:
        symbol = str(row["symbol"])
        repeat_index[symbol] += 1
        old_midpoint = (
            Decimal(row["old_core_mrz_lower"]) + Decimal(row["old_core_mrz_upper"])
        ) / Decimal("2")
        direction = _migration_direction(row)
        occurred_at = row["occurred_at"]
        evidence_times.append(occurred_at)
        previous_route = str(row["previous_route_owner"])
        new_route = str(row["route_owner"])
        events.append({
            "event_key": str(row["event_key"]),
            "sequence": int(row["sequence"]),
            "symbol": symbol,
            "occurred_at": _iso(occurred_at),
            "direction": direction,
            "previous_route_owner": previous_route,
            "route_owner": new_route,
            "route_changed": previous_route != new_route,
            "old_lower": _decimal_text(row["old_core_mrz_lower"]),
            "old_upper": _decimal_text(row["old_core_mrz_upper"]),
            "old_midpoint": _decimal_text(old_midpoint),
            "new_lower": _decimal_text(row["new_core_mrz_lower"]),
            "new_upper": _decimal_text(row["new_core_mrz_upper"]),
            "new_midpoint": _decimal_text(row["new_core_mrz_midpoint"]),
            "new_structural_location": str(row["structural_location"]),
            "trigger_observation_event_id": str(row["trigger_event_id"]),
            "repeat_index": repeat_index[symbol],
        })
    events.sort(
        key=lambda item: (item["occurred_at"], item["sequence"], item["event_key"]),
        reverse=True,
    )
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_symbol[event["symbol"]].append(event)
    contributors = []
    for symbol, symbol_events in sorted(by_symbol.items()):
        directions = {event["direction"] for event in symbol_events}
        contributors.append({
            "symbol": symbol,
            "event_count": len(symbol_events),
            "directions": sorted(directions),
            "first_at": min(event["occurred_at"] for event in symbol_events),
            "latest_at": max(event["occurred_at"] for event in symbol_events),
            "event_keys": [event["event_key"] for event in symbol_events],
        })
    earliest = min(evidence_times) if evidence_times else None
    latest = max(evidence_times) if evidence_times else None
    summary = {
        "unique_contributors": len(contributors),
        "unique_higher_contributors": sum(
            "higher" in item["directions"] for item in contributors
        ),
        "unique_lower_contributors": sum(
            "lower" in item["directions"] for item in contributors
        ),
        "event_count": len(events),
        "higher_events": sum(event["direction"] == "higher" for event in events),
        "lower_events": sum(event["direction"] == "lower" for event in events),
        "same_midpoint_events": sum(
            event["direction"] == "same_midpoint" for event in events
        ),
        "repeated_contributors": sum(item["event_count"] > 1 for item in contributors),
        "both_direction_contributors": sum(len(item["directions"]) > 1 for item in contributors),
        "route_change_events": sum(event["route_changed"] for event in events),
        "earliest_at": _iso(earliest),
        "latest_at": _iso(latest),
        "span_seconds": (latest - earliest).total_seconds() if earliest and latest and len(events) > 1 else None,
    }
    if (
        summary["event_count"] != len(events)
        or summary["unique_contributors"] != len(contributors)
        or summary["higher_events"]
        + summary["lower_events"]
        + summary["same_midpoint_events"]
        != summary["event_count"]
    ):
        raise ValueError("migration evidence does not reconcile")
    return ({
        "status": "available",
        "summary": summary,
        "contributors": contributors,
        "events": events,
    }, evidence_times)


def _mrz_activity_records(
    members: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    member_set = set(members)
    records: list[dict[str, Any]] = []
    for row in rows:
        symbol = str(row["symbol"])
        if symbol not in member_set:
            continue
        event_type = str(row["event_type"])
        direction = None
        if event_type == "MRZ_MIGRATED" and row.get("old_core_mrz_lower") is not None:
            direction = _migration_direction(row)
        records.append({
            "id": f"mrz:{row['event_key']}",
            "tracker": "mrz",
            "event_type": event_type,
            "symbol": symbol,
            "occurred_at": _iso(row["occurred_at"]),
            "direction": direction,
            "route_owner": str(row["route_owner"]),
            "previous_route_owner": row.get("previous_route_owner"),
            "route_changed": event_type == "ROUTE_CHANGED" or (
                row.get("previous_route_owner") is not None
                and str(row["previous_route_owner"]) != str(row["route_owner"])
            ),
            "source_event_id": str(row["event_key"]),
            "trigger_observation_event_id": str(row["trigger_event_id"]),
            "timestamp_semantics": "canonical_mrz_event_timestamp",
        })
    records.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    return records


def _activity(
    members: Sequence[str],
    location_activity: Mapping[str, Any],
    mrz_records: Sequence[Mapping[str, Any]],
    pressure: Mapping[str, Any],
    near_miss: Mapping[str, Any],
    comparison_at: datetime,
    as_of: datetime,
) -> dict[str, Any]:
    records = [dict(item) for item in location_activity.get("records", ())]
    records.extend(dict(item) for item in mrz_records)
    episode_keys: set[str] = set()
    for episode in near_miss.get("episodes", ()):
        if episode["started_in_window"]:
            episode_keys.add(episode["episode_key"])
            records.append({
                "id": f"near-miss:{episode['episode_key']}:started",
                "tracker": "near_miss",
                "event_type": "NEAR_MISS_EPISODE_STARTED",
                "symbol": episode["symbol"],
                "occurred_at": episode["started_at"],
                "lifecycle": "started",
                "route_owner": episode["route_owner"],
                "source_event_id": episode["episode_key"],
                "timestamp_semantics": "canonical_episode_start_timestamp",
            })
        ended_at = episode.get("ended_at")
        if ended_at and _iso(comparison_at) < ended_at <= _iso(as_of):
            episode_keys.add(episode["episode_key"])
            records.append({
                "id": f"near-miss:{episode['episode_key']}:ended",
                "tracker": "near_miss",
                "event_type": "NEAR_MISS_EPISODE_ENDED",
                "symbol": episode["symbol"],
                "occurred_at": ended_at,
                "lifecycle": "ended",
                "ended_reason": episode.get("ended_reason"),
                "route_owner": episode["route_owner"],
                "source_event_id": episode["episode_key"],
                "timestamp_semantics": "canonical_episode_end_timestamp",
            })
    records.sort(key=lambda item: (item["occurred_at"], item["id"]), reverse=True)
    unique_records = {item["id"]: item for item in records}
    records = sorted(
        unique_records.values(),
        key=lambda item: (item["occurred_at"], item["id"]),
        reverse=True,
    )
    by_tracker = {
        tracker: sum(item["tracker"] == tracker for item in records)
        for tracker in ("ipda", "mrz", "near_miss", "ote")
    }
    location_records = [item for item in records if item["tracker"] == "ipda"]
    tracker_records = [item for item in records if item["tracker"] != "ipda"]
    coverage = location_activity.get("coverage", {})
    full_ipda_coverage = bool(members) and coverage.get("fresh_comparable") == len(members)
    if records:
        classification = "changed"
    elif full_ipda_coverage:
        classification = "no_change"
    else:
        classification = "insufficient_data"
    return {
        "status": classification,
        "window": {
            "comparison_at": _iso(comparison_at),
            "as_of": _iso(as_of),
        },
        "latest_at": records[0]["occurred_at"] if records else None,
        "records": records,
        "summary": {
            "record_count": len(records),
            "unique_symbol_count": len({item["symbol"] for item in records}),
            "ipda_location_change_count": len(location_records),
            "ipda_unique_symbol_count": len({item["symbol"] for item in location_records}),
            "tracker_event_count": len(tracker_records),
            "near_miss_episode_count": len(episode_keys),
            "by_tracker": by_tracker,
            "moved_higher_symbols": len({
                item["symbol"] for item in location_records
                if item.get("direction") == "higher"
            }),
            "moved_lower_symbols": len({
                item["symbol"] for item in location_records
                if item.get("direction") == "lower"
            }),
        },
        "coverage": {
            "ipda": {
                **coverage,
                "status": "verified" if full_ipda_coverage else (
                    "partial" if coverage.get("fresh_comparable") else "unavailable"
                ),
                "semantics": "baseline_plus_fresh_comparable_observation",
            },
            "mrz": {
                "status": "event_history_available",
                "semantics": "event_presence_only_no_independent_freshness_heartbeat",
            },
            "near_miss": {
                "status": "episode_history_available",
                "semantics": "episode_lifecycle_records",
            },
            "ote": dict(OTE_NOT_CONNECTED),
        },
        "classification_basis": (
            "qualifying_recorded_change"
            if classification == "changed"
            else "complete_fresh_ipda_comparison_no_transition"
            if classification == "no_change"
            else "incomplete_fresh_comparison_coverage"
        ),
    }


def build_named_group_evidence(
    inputs: Mapping[str, Any],
    group: Mapping[str, Any],
) -> dict[str, Any]:
    members = tuple(str(symbol) for symbol in group.get("members", ()))
    member_set = set(members)
    endpoints = {
        str(row["symbol"]): row
        for row in inputs.get("endpoint_rows", ())
        if str(row["symbol"]) in member_set
    }
    active_mrzs = tuple(
        active for active in inputs.get("active_mrzs", ()) if active.symbol in member_set
    )
    observations = tuple(
        observation
        for observation in inputs.get("observations", ())
        if observation.symbol in member_set
    )
    comparison_at = inputs["comparison_at"]
    status = "available"
    limitations = list(LIMITATIONS)
    evidence_times: list[datetime] = []

    try:
        structural, structural_coverage, times = _structural(
            members, endpoints, comparison_at
        )
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        structural = {"status": "unavailable", "reason": "structural_projection_failed"}
        structural_coverage = {
            "structural_current_available": None,
            "structural_comparable": None,
            "structural_fresh_in_window": None,
            "structural_no_new_observation": None,
            "structural_unavailable_current": None,
        }

    try:
        current_pressure, pressure_coverage, current_by_symbol, times = _current_pressure(
            group,
            members,
            endpoints,
            active_mrzs,
            observations,
            comparison_at,
        )
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        current_pressure = {"status": "unavailable", "reason": "current_pressure_projection_failed"}
        pressure_coverage = {
            "current_pressure_evaluated": None,
            "current_pressure_active_mrz": None,
            "current_pressure_directional": None,
            "current_pressure_evidence_fresh_in_window": None,
        }
        current_by_symbol = {}

    try:
        cumulative, times = _pressure_events(
            members, inputs.get("pressure_events", ()), current_by_symbol
        )
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        cumulative = {"status": "unavailable", "reason": "cumulative_event_projection_failed"}

    try:
        latest_directional, times = _pressure_events(
            members, inputs.get("latest_pressure_events", ()), current_by_symbol
        )
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        latest_directional = {
            "status": "unavailable",
            "reason": "latest_directional_event_projection_failed",
        }

    try:
        migrations, times = _migrations(members, inputs.get("migration_events", ()))
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        migrations = {"status": "unavailable", "reason": "migration_projection_failed"}

    try:
        location_history = _location_history(
            members,
            endpoints,
            inputs.get("location_observations", ()),
            comparison_at,
            inputs["as_of"],
        )
    except Exception:
        status = "partial"
        location_history = {
            "status": "unavailable",
            "reason": "location_history_projection_failed",
            "message": "Historical location data unavailable for current members.",
        }

    try:
        location_activity = _location_activity(
            members,
            endpoints,
            inputs.get("location_observations", ()),
            comparison_at,
            inputs["as_of"],
        )
    except Exception:
        status = "partial"
        location_activity = {
            "status": "unavailable",
            "records": [],
            "coverage": {
                "member_total": len(members),
                "comparison_available": 0,
                "fresh_comparable": 0,
                "insufficient": len(members),
                "members": [],
            },
        }

    try:
        near_miss = _near_misses(
            members,
            inputs.get("near_miss_episodes", ()),
            comparison_at,
            inputs["as_of"],
        )
        evidence_times.extend(
            row["started_at"] for row in inputs.get("near_miss_episodes", ())
            if str(row["symbol"]) in member_set
        )
    except Exception:
        status = "partial"
        near_miss = {"status": "unavailable", "reason": "near_miss_projection_failed"}

    try:
        mrz_activity_records = _mrz_activity_records(
            members, inputs.get("mrz_activity_events", ())
        )
        activity = _activity(
            members,
            location_activity,
            mrz_activity_records,
            cumulative,
            near_miss,
            comparison_at,
            inputs["as_of"],
        )
        for record in activity["records"]:
            occurred_at = datetime.fromisoformat(record["occurred_at"].replace("Z", "+00:00"))
            evidence_times.append(occurred_at)
    except Exception:
        status = "partial"
        activity = {
            "status": "insufficient_data",
            "latest_at": None,
            "records": [],
            "summary": {
                "record_count": None,
                "unique_symbol_count": None,
                "ipda_location_change_count": None,
                "ipda_unique_symbol_count": None,
                "tracker_event_count": None,
                "near_miss_episode_count": None,
                "by_tracker": {},
            },
            "coverage": {
                "ipda": location_activity.get("coverage", {}),
                "ote": dict(OTE_NOT_CONNECTED),
            },
            "classification_basis": "activity_projection_failed",
        }

    active_by_symbol = {active.symbol: active for active in active_mrzs}
    structural_by_symbol = {
        item["symbol"]: item for item in structural.get("contributors", ())
    }
    unavailable_structural = {
        item["symbol"]: item for item in structural.get("unavailable_members", ())
    }
    near_miss_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in near_miss.get("episodes", ()):
        near_miss_by_symbol[episode["symbol"]].append(episode)
    latest_pressure_by_symbol = {
        item["symbol"]: item
        for item in latest_directional.get("latest_by_member", ())
    }
    latest_observation_by_symbol: dict[str, Observation] = {}
    for observation in inputs.get("location_observations", ()):
        if observation.symbol in member_set:
            current = latest_observation_by_symbol.get(observation.symbol)
            if current is None or observation.observed_at > current.observed_at:
                latest_observation_by_symbol[observation.symbol] = observation
    member_rows = []
    for symbol in sorted(members):
        pressure = current_by_symbol.get(symbol, {})
        active = active_by_symbol.get(symbol)
        movement = structural_by_symbol.get(symbol, {})
        endpoint = endpoints.get(symbol, {})
        current_location = movement.get("current_location") or _location(endpoint, "current")
        latest_near_miss = next(
            (item for item in near_miss_by_symbol.get(symbol, ()) if item["active"]),
            near_miss_by_symbol.get(symbol, [None])[0],
        )
        latest_observation = latest_observation_by_symbol.get(symbol)
        last_pressure = latest_pressure_by_symbol.get(symbol, {})
        member_rows.append({
            "symbol": symbol,
            "route": (
                active.route_owner.value
                if active
                else latest_observation.route.value if latest_observation else None
            ),
            "location": current_location,
            "location_label": LOCATION_LABELS.get(current_location, "Unavailable"),
            "mrz_status": "Active" if active else "Inactive",
            "mrz": (
                {
                    "status": "active",
                    "lower": _decimal_text(active.core_mrz_lower),
                    "upper": _decimal_text(active.core_mrz_upper),
                    "midpoint": _decimal_text(active.core_mrz_midpoint),
                    "activated_at": _iso(active.activated_at),
                    "activation_event_id": active.activation_event_id,
                    "activation_source": active.activation_source.value,
                    "route_owner": active.route_owner.value,
                }
                if active
                else {
                    "status": "inactive",
                    "lower": None,
                    "upper": None,
                    "midpoint": None,
                    "activated_at": None,
                    "activation_event_id": None,
                    "activation_source": None,
                    "route_owner": None,
                }
            ),
            "pressure": pressure.get("direction"),
            "pressure_label": pressure.get("direction_label") or pressure.get("direction"),
            "current_pressure": pressure,
            "pressure_evidence_at": pressure.get("evidence", {}).get(
                "latest_pressure_observed_at"
            ),
            "last_pressure_direction": last_pressure.get("event_direction"),
            "last_pressure_event_at": last_pressure.get("occurred_at"),
            "last_pressure_event_id": last_pressure.get("event_id"),
            "last_pressure_vs_current": last_pressure.get("comparison"),
            "near_miss": latest_near_miss,
            "ote": dict(OTE_NOT_CONNECTED),
            "current_observed_at": _iso(endpoint.get("current_observed_at")),
            "structural_available": symbol not in unavailable_structural,
        })

    return {
        "contract_version": CONTRACT_VERSION,
        "scope": "named_group",
        "pressure_compatibility": {
            "status": "deprecated_read_only",
            "operational": False,
            "consumed_by_active_ui": False,
        },
        "status": status,
        "group": {
            "id": int(group["id"]),
            "name": str(group["name"]),
            "members": list(members),
            "member_count": len(members),
            "created_at": _iso(group.get("created_at")),
            "updated_at": _iso(group.get("updated_at")),
        },
        "window": _snapshot(inputs),
        "membership_semantics": "current_membership_at_snapshot",
        "latest_relevant_evidence_at": _iso(max(evidence_times)) if evidence_times else None,
        "coverage": {**structural_coverage, **pressure_coverage},
        "structural": structural,
        "location_history": location_history,
        "activity": activity,
        "near_miss": near_miss,
        "ote": dict(OTE_NOT_CONNECTED),
        "members": member_rows,
        "directional": {
            "current_pressure": current_pressure,
            "cumulative_lifecycle_pressure_events": cumulative,
            "latest_pressure_events": latest_directional,
            "mrz_migrations": migrations,
        },
        "limitations": limitations,
    }


def _summary_group(detail: Mapping[str, Any]) -> dict[str, Any]:
    structural = detail.get("structural", {})
    directional = detail.get("directional", {})
    current = directional.get("current_pressure", {})
    cumulative = directional.get("cumulative_lifecycle_pressure_events", {})
    latest_directional = directional.get("latest_pressure_events", {})
    migrations = directional.get("mrz_migrations", {})
    group = detail["group"]
    return {
        "id": group["id"],
        "name": group["name"],
        "updated_at": group["updated_at"],
        "membership_total": group["member_count"],
        "latest_relevant_evidence_at": detail.get("latest_relevant_evidence_at"),
        "coverage": detail.get("coverage", {}),
        "activity": {
            key: value
            for key, value in detail.get("activity", {}).items()
            if key != "records"
        },
        "structural": {
            **structural.get("summary", {"status": "unavailable"}),
            "current_distribution": structural.get("current_distribution"),
        },
        "directional": {
            "current_pressure": current.get("summary", {"status": "unavailable"}),
            "latest_cumulative_event": latest_directional.get("summary", {}).get(
                "latest_event", {"status": "unavailable"}
            ),
            "latest_event_vs_current": latest_directional.get("summary", {}).get(
                "latest_event_vs_current", {"status": "unavailable"}
            ),
            "cumulative_event_count": cumulative.get("summary", {}).get("event_count"),
        },
        "migrations": migrations.get("summary", {"status": "unavailable"}),
        "near_miss": detail.get("near_miss", {"status": "unavailable"}),
        "ote": detail.get("ote", dict(OTE_NOT_CONNECTED)),
        "status": detail.get("status", "available"),
        "limitations": [],
    }


def build_all_groups_evidence(inputs: Mapping[str, Any]) -> dict[str, Any]:
    groups = sorted(
        inputs.get("groups", ()),
        key=lambda group: (str(group["name"]).casefold(), int(group["id"])),
    )
    details = [build_named_group_evidence(inputs, group) for group in groups]
    unique_members = {
        str(symbol) for group in groups for symbol in group.get("members", ())
    }
    migration_keys = {
        event["event_key"]
        for detail in details
        for event in detail.get("directional", {}).get("mrz_migrations", {}).get("events", ())
    }
    appearances = sum(
        len(detail.get("directional", {}).get("mrz_migrations", {}).get("events", ()))
        for detail in details
    )
    activity_records = {
        record["id"]: record
        for detail in details
        for record in detail.get("activity", {}).get("records", ())
    }
    location_records = [
        record for record in activity_records.values() if record["tracker"] == "ipda"
    ]
    tracker_records = [
        record for record in activity_records.values()
        if record["tracker"] not in {"ipda", "pressure"}
    ]
    status = "partial" if any(detail.get("status") == "partial" for detail in details) else "available"
    return {
        "contract_version": CONTRACT_VERSION,
        "scope": "all_groups",
        "pressure_compatibility": {
            "status": "deprecated_read_only",
            "operational": False,
            "consumed_by_active_ui": False,
        },
        "status": status,
        "window": _snapshot(inputs),
        "membership_semantics": "current_membership_at_snapshot",
        "scope_totals": {
            "group_count": len(groups),
            "member_slots": sum(len(group.get("members", ())) for group in groups),
            "unique_members": len(unique_members),
            "canonical_migration_events": len(migration_keys),
            "group_context_migration_appearances": appearances,
        },
        "activity_summary": {
            "groups_with_activity": sum(
                detail.get("activity", {}).get("status") == "changed"
                for detail in details
            ),
            "group_count": len(groups),
            "ipda_location_change_symbols": len({
                record["symbol"] for record in location_records
            }),
            "ipda_location_change_records": len(location_records),
            "ipda_moved_higher_symbols": len({
                record["symbol"] for record in location_records
                if record.get("direction") == "higher"
            }),
            "ipda_moved_lower_symbols": len({
                record["symbol"] for record in location_records
                if record.get("direction") == "lower"
            }),
            "new_tracker_events": len(tracker_records),
            "tracker_event_breakdown": {
                tracker: sum(record["tracker"] == tracker for record in tracker_records)
                for tracker in ("mrz", "near_miss", "ote")
            },
            "changed_groups": sum(
                detail.get("activity", {}).get("status") == "changed"
                for detail in details
            ),
            "no_change_groups": sum(
                detail.get("activity", {}).get("status") == "no_change"
                for detail in details
            ),
            "insufficient_data_groups": sum(
                detail.get("activity", {}).get("status") == "insufficient_data"
                for detail in details
            ),
        },
        "ote": dict(OTE_NOT_CONNECTED),
        "groups": [_summary_group(detail) for detail in details],
        "empty_state": "No saved groups." if not groups else None,
        "limitations": list(LIMITATIONS),
    }
