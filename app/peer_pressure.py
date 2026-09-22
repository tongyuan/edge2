from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain import ActiveMRZ, Observation
from app.mrz_robustness import post_activation_snapshot


PRESSURE_DIRECTIONS = ("higher", "lower", "neutral")
PRIMARY_PRESSURE_LOCATIONS = (
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
    "below_ipda_range": "Below IPDA Range",
    "above_ipda_range": "Above IPDA Range",
    "deep_discount_core_mrz": "Deep Discount",
    "shallow_discount_core_mrz": "Shallow Discount",
    "shallow_premium_core_mrz": "Shallow Premium",
    "deep_premium_core_mrz": "Deep Premium",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _location_label(value: object) -> str:
    if value is None:
        return "Unavailable"
    return LOCATION_LABELS.get(str(value), "Unavailable")


def _headline(higher: int, lower: int) -> dict[str, str]:
    if higher + lower == 0:
        return {
            "status": "INSUFFICIENT_PARTICIPATION",
            "direction": "NEUTRAL",
            "label": "Insufficient Participation",
        }
    if higher > lower:
        return {
            "status": "UPWARD_PRESSURE",
            "direction": "UP",
            "label": "Upward Pressure",
        }
    if lower > higher:
        return {
            "status": "DOWNWARD_PRESSURE",
            "direction": "DOWN",
            "label": "Downward Pressure",
        }
    return {
        "status": "MIXED_BALANCED",
        "direction": "NEUTRAL",
        "label": "Mixed / Balanced",
    }


def _symbol_pressure_state(
    symbol: str,
    member_state: Mapping[str, Any],
    active_by_symbol: Mapping[str, ActiveMRZ],
    observations_by_symbol: Mapping[str, Sequence[Observation]],
) -> dict[str, Any]:
    """Classify one symbol through the canonical current-pressure path."""
    current_location = member_state.get("current_location")
    latest_observed_at = member_state.get("latest_observed_at")
    active = active_by_symbol.get(symbol)

    if active is None:
        direction = "neutral"
        evidence = {
            "status": "NO_ACTIVE_MRZ",
            "label": "Neutral",
            "reason": (
                "No active authoritative MRZ is available, so directional "
                "pressure is not established."
            ),
            "observed_at": None,
            "current_pressure_since": None,
            "latest_pressure_observed_at": None,
            "recent_sequence": [],
            "recent_higher_observation_count": 0,
            "recent_lower_observation_count": 0,
            "post_activation_observation_count": 0,
            "higher_observation_count": 0,
            "lower_observation_count": 0,
        }
        active_payload = {
            "status": "unestablished",
            "route_owner": None,
            "location": None,
            "location_label": "Unavailable",
            "activated_at": None,
        }
    else:
        snapshot = post_activation_snapshot(
            active,
            observations_by_symbol.get(symbol, ()),
        )
        current_pressure = snapshot.current_pressure
        direction = {
            "UP": "higher",
            "DOWN": "lower",
        }.get(current_pressure.state.direction, "neutral")
        current_pressure_since = _iso(current_pressure.current_pressure_since)
        latest_pressure_observed_at = _iso(
            current_pressure.latest_pressure_observed_at
        )
        evidence = {
            "status": current_pressure.state.status,
            "label": current_pressure.state.label,
            "reason": current_pressure.state.reason,
            "observed_at": current_pressure_since,
            "current_pressure_since": current_pressure_since,
            "latest_pressure_observed_at": latest_pressure_observed_at,
            "recent_sequence": [
                {
                    "direction": item.direction,
                    "observed_at": _iso(item.observation.observed_at),
                }
                for item in current_pressure.recent_evidence
            ],
            "recent_higher_observation_count": (
                current_pressure.recent_higher_count
            ),
            "recent_lower_observation_count": (
                current_pressure.recent_lower_count
            ),
            "post_activation_observation_count": snapshot.total_observation_count,
            "higher_observation_count": snapshot.above_envelope_count,
            "lower_observation_count": snapshot.below_envelope_count,
        }
        active_payload = {
            "status": "active",
            "route_owner": active.route_owner.value,
            "location": active.structural_location.value,
            "location_label": _location_label(active.structural_location.value),
            "activated_at": _iso(active.activated_at),
        }

    return {
        "symbol": symbol,
        "direction": direction,
        "direction_label": direction.title(),
        "current_location": current_location,
        "current_location_label": _location_label(current_location),
        "latest_observed_at": latest_observed_at,
        "active_mrz": active_payload,
        "evidence": evidence,
    }


def _build_pressure_report(
    *,
    report_id: int | None,
    name: str,
    members: Sequence[str],
    member_states: Mapping[str, Mapping[str, Any]],
    active_mrzs: Sequence[ActiveMRZ],
    observations: Sequence[Observation],
) -> dict[str, Any]:
    """Derive transparent pressure for any scope from one symbol classifier."""
    active_by_symbol = {active.symbol: active for active in active_mrzs}
    observations_by_symbol: dict[str, list[Observation]] = {}
    for observation in observations:
        observations_by_symbol.setdefault(observation.symbol, []).append(observation)
    categories: dict[str, list[dict[str, Any]]] = {
        direction: [] for direction in PRESSURE_DIRECTIONS
    }
    evidence_times: list[str] = []

    for symbol in members:
        state = _symbol_pressure_state(
            symbol,
            member_states.get(symbol, {}),
            active_by_symbol,
            observations_by_symbol,
        )
        evidence_time = (
            state["evidence"]["latest_pressure_observed_at"]
            or state["latest_observed_at"]
        )
        if evidence_time:
            evidence_times.append(str(evidence_time))
        categories[state["direction"]].append(state)

    counts = {
        direction: len(categories[direction])
        for direction in PRESSURE_DIRECTIONS
    }
    total = len(members)
    participation = counts["higher"] + counts["lower"]
    if sum(counts.values()) != total:
        raise ValueError("pressure categories must reconcile to scope membership")

    return {
        "id": report_id,
        "name": name,
        "members": list(members),
        "member_count": total,
        "as_of": max(evidence_times) if evidence_times else None,
        "headline": _headline(counts["higher"], counts["lower"]),
        "counts": counts,
        "participation": {
            "count": participation,
            "total": total,
        },
        "categories": categories,
        "method": {
            "source": "canonical chronological outside-envelope observations for the current active MRZ episode",
            "higher": "At least three of the latest four qualifying pressure observations are Higher.",
            "lower": "At least three of the latest four qualifying pressure observations are Lower.",
            "neutral": "No active MRZ, fewer than three qualifying observations, or no side holds three of the latest four.",
            "headline": (
                "Strict Higher/Lower count leader; a tie is Mixed / Balanced; "
                "zero directional participation is Insufficient Participation."
            ),
        },
    }


def build_peer_pressure_report(
    group: Mapping[str, Any],
    active_mrzs: Sequence[ActiveMRZ],
    observations: Sequence[Observation],
) -> dict[str, Any]:
    """Derive saved-cohort pressure through the shared scope builder."""
    current_members = {
        str(item["symbol"]): item
        for item in group.get("current_state", {}).get("members", ())
    }
    return _build_pressure_report(
        report_id=int(group["id"]),
        name=str(group["name"]),
        members=tuple(str(symbol) for symbol in group["members"]),
        member_states=current_members,
        active_mrzs=active_mrzs,
        observations=observations,
    )


def build_universe_pressure_report(
    symbol_states: Sequence[Mapping[str, Any]],
    active_mrzs: Sequence[ActiveMRZ],
    observations: Sequence[Observation],
) -> dict[str, Any]:
    """Build breadth and location matrix for the classified monitor universe."""
    member_states = {
        str(item["symbol"]): {
            "symbol": str(item["symbol"]),
            "current_location": item.get("current_price_location"),
            "latest_observed_at": item.get("latest_observed_at"),
        }
        for item in symbol_states
    }
    classified_members = tuple(
        symbol
        for symbol, state in member_states.items()
        if state["current_location"] in PRIMARY_PRESSURE_LOCATIONS
    )
    report = _build_pressure_report(
        report_id=None,
        name="Monitored universe",
        members=classified_members,
        member_states=member_states,
        active_mrzs=active_mrzs,
        observations=observations,
    )

    rows: dict[str, dict[str, Any]] = {}
    for location in PRIMARY_PRESSURE_LOCATIONS:
        counts = {
            direction: sum(
                item["current_location"] == location
                for item in report["categories"][direction]
            )
            for direction in PRESSURE_DIRECTIONS
        }
        total = sum(counts.values())
        rows[location] = {
            "counts": counts,
            "participation": {
                "count": counts["higher"] + counts["lower"],
                "total": total,
            },
        }

    matrix_totals = {
        direction: sum(row["counts"][direction] for row in rows.values())
        for direction in PRESSURE_DIRECTIONS
    }
    if matrix_totals != report["counts"]:
        raise ValueError("pressure map must reconcile to pressure breadth")
    matrix_population = sum(
        row["participation"]["total"] for row in rows.values()
    )
    if matrix_population != report["member_count"]:
        raise ValueError("pressure map must reconcile to classified population")

    return {
        **report,
        "scope": "monitored_universe",
        "pressure_map": {
            "locations": rows,
            "totals": matrix_totals,
        },
        "excluded_unclassified_count": len(symbol_states) - len(classified_members),
    }
