from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain import ActiveMRZ, Observation
from app.mrz_robustness import post_activation_snapshot


PRESSURE_DIRECTIONS = ("higher", "lower", "neutral")

LOCATION_LABELS = {
    "deep_discount": "Deep Discount",
    "shallow_discount": "Shallow Discount",
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


def build_peer_pressure_report(
    group: Mapping[str, Any],
    active_mrzs: Sequence[ActiveMRZ],
    observations: Sequence[Observation],
) -> dict[str, Any]:
    """Derive transparent cohort pressure from the shared canonical classifier."""
    active_by_symbol = {active.symbol: active for active in active_mrzs}
    observations_by_symbol: dict[str, list[Observation]] = {}
    for observation in observations:
        observations_by_symbol.setdefault(observation.symbol, []).append(observation)

    current_members = {
        str(item["symbol"]): item
        for item in group.get("current_state", {}).get("members", ())
    }
    categories: dict[str, list[dict[str, Any]]] = {
        direction: [] for direction in PRESSURE_DIRECTIONS
    }
    evidence_times: list[str] = []

    for symbol in group["members"]:
        member_state = current_members.get(symbol, {})
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
            direction = {
                "UP": "higher",
                "DOWN": "lower",
            }.get(snapshot.state.direction, "neutral")
            pressure_observed_at = (
                _iso(snapshot.observations[-1].observed_at)
                if snapshot.observations
                else None
            )
            evidence = {
                "status": snapshot.state.status,
                "label": snapshot.state.label,
                "reason": snapshot.state.reason,
                "observed_at": pressure_observed_at,
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

        if evidence["observed_at"]:
            evidence_times.append(str(evidence["observed_at"]))
        elif latest_observed_at:
            evidence_times.append(str(latest_observed_at))

        categories[direction].append(
            {
                "symbol": symbol,
                "direction": direction,
                "direction_label": direction.title(),
                "current_location": current_location,
                "current_location_label": _location_label(current_location),
                "latest_observed_at": latest_observed_at,
                "active_mrz": active_payload,
                "evidence": evidence,
            }
        )

    counts = {
        direction: len(categories[direction])
        for direction in PRESSURE_DIRECTIONS
    }
    total = len(group["members"])
    participation = counts["higher"] + counts["lower"]
    if sum(counts.values()) != total:
        raise ValueError("peer pressure categories must reconcile to group membership")

    return {
        "id": group["id"],
        "name": group["name"],
        "members": list(group["members"]),
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
            "source": "canonical post-activation observations versus the frozen active MRZ migration envelope",
            "higher": "Existing shared pressure classifier returns UP.",
            "lower": "Existing shared pressure classifier returns DOWN.",
            "neutral": "No active MRZ, no usable evidence, or no material directional dominance.",
            "headline": (
                "Strict Higher/Lower count leader; a tie is Mixed / Balanced; "
                "zero directional participation is Insufficient Participation."
            ),
        },
    }
