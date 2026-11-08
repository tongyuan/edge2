from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain import ActiveMRZ, Observation
from app.peer_pressure import build_peer_pressure_report
from app.structure import classify_ipda_location


CONTRACT_VERSION = "stage-a-1"
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
    "at_eqm": "At EQM",
    "shallow_premium": "Shallow Premium",
    "deep_premium": "Deep Premium",
}
PRESSURE_ORDER = {"higher": 0, "lower": 1, "neutral": 2}
LIMITATIONS = [
    "Historical evidence is attributed to membership at the response snapshot.",
    "Current pressure is a present snapshot, not a windowed historical series.",
    "No staleness, materiality, diagnosis, lifecycle, or resolution rule is applied.",
]


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
        migrations, times = _migrations(members, inputs.get("migration_events", ()))
        evidence_times.extend(times)
    except Exception:
        status = "partial"
        migrations = {"status": "unavailable", "reason": "migration_projection_failed"}

    return {
        "contract_version": CONTRACT_VERSION,
        "scope": "named_group",
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
        "directional": {
            "current_pressure": current_pressure,
            "cumulative_lifecycle_pressure_events": cumulative,
            "mrz_migrations": migrations,
        },
        "limitations": limitations,
    }


def _summary_group(detail: Mapping[str, Any]) -> dict[str, Any]:
    structural = detail.get("structural", {})
    directional = detail.get("directional", {})
    current = directional.get("current_pressure", {})
    cumulative = directional.get("cumulative_lifecycle_pressure_events", {})
    migrations = directional.get("mrz_migrations", {})
    group = detail["group"]
    return {
        "id": group["id"],
        "name": group["name"],
        "updated_at": group["updated_at"],
        "membership_total": group["member_count"],
        "latest_relevant_evidence_at": detail.get("latest_relevant_evidence_at"),
        "coverage": detail.get("coverage", {}),
        "structural": structural.get("summary", {"status": "unavailable"}),
        "directional": {
            "current_pressure": current.get("summary", {"status": "unavailable"}),
            "latest_cumulative_event": cumulative.get("summary", {}).get(
                "latest_event", {"status": "unavailable"}
            ),
            "latest_event_vs_current": cumulative.get("summary", {}).get(
                "latest_event_vs_current", {"status": "unavailable"}
            ),
            "cumulative_event_count": cumulative.get("summary", {}).get("event_count"),
        },
        "migrations": migrations.get("summary", {"status": "unavailable"}),
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
    status = "partial" if any(detail.get("status") == "partial" for detail in details) else "available"
    return {
        "contract_version": CONTRACT_VERSION,
        "scope": "all_groups",
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
        "groups": [_summary_group(detail) for detail in details],
        "empty_state": "No saved groups." if not groups else None,
        "limitations": list(LIMITATIONS),
    }
