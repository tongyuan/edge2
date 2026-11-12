from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

from app.domain import Observation, Route
from app.mrz_robustness import classify_current_pressure_directions
from app.structure import classify_ipda_location


RULE_VERSION = "opportunity-intelligence-phase-1.0"
STATE_LABELS = {
    "CONTEXT_OBSERVED": "Context Observed",
    "DEVELOPING": "Developing",
    "NEAR_MISS": "Near Miss",
    "STRUCTURE_ESTABLISHED": "Structure Established",
    "REASSESSMENT": "Reassessment",
    "HISTORICAL_UNRESOLVED": "Historical / Unresolved",
}
STATE_RANK = {
    "REASSESSMENT": 6,
    "STRUCTURE_ESTABLISHED": 5,
    "NEAR_MISS": 4,
    "DEVELOPING": 3,
    "CONTEXT_OBSERVED": 2,
    "HISTORICAL_UNRESOLVED": 1,
}


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def decimal_text(value: Any | None) -> str | None:
    return None if value is None else format(Decimal(value), "f")


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _as_known_at(value: datetime | None, fallback: datetime) -> datetime:
    snapshot_at = _utc(fallback)
    return min(_utc(value or snapshot_at), snapshot_at)


def _episode_id(symbol: str, route: str, origin_event_id: str) -> str:
    material = f"{symbol}|{route}|{origin_event_id}|{RULE_VERSION}".encode()
    return f"opp-{hashlib.sha256(material).hexdigest()[:20]}"


def _location(observation: Observation) -> str | None:
    location = classify_ipda_location(
        observation.observation_price,
        observation.ipda_20w_high,
        observation.ipda_20w_low,
    )
    return location.value if location is not None else None


def _location_label(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("_", " ").title().replace("Eqm", "EQM").replace("Ipda", "IPDA")


def _observation_event(observation: Observation) -> dict[str, Any]:
    location = _location(observation)
    return {
        "source_tracker": "IPDA_ROUTE",
        "event_type": f"{observation.route.value}_{observation.observation_type.value.upper()}",
        "canonical_event_id": observation.event_id,
        "symbol": observation.symbol,
        "route": observation.route.value,
        "observation_type": observation.observation_type.value,
        "effective_at": iso(observation.observed_at),
        "known_at": iso(observation.received_at),
        "price": decimal_text(observation.observation_price),
        "lower_bound": None,
        "upper_bound": None,
        "ipda_location": location,
        "ipda_location_label": _location_label(location),
        "ipda_20w_low": decimal_text(observation.ipda_20w_low),
        "ipda_20w_high": decimal_text(observation.ipda_20w_high),
    }


def _near_miss_event(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not row.get("canonical_snapshot_reliable"):
        return None
    return {
        "source_tracker": "NEAR_MISS",
        "event_type": "MRZ_NEAR_MISS",
        "canonical_event_id": str(
            row.get("canonical_candidate_identity")
            or row.get("episode_key")
            or row["id"]
        ),
        "source_event_id": (
            str(row["canonical_candidate_event_id"])
            if row.get("canonical_candidate_event_id")
            else None
        ),
        "symbol": str(row["symbol"]),
        "route": str(row["route_owner"]),
        "effective_at": iso(row.get("canonical_candidate_timestamp") or row["started_at"]),
        "known_at": iso(row["started_at"]),
        "ended_at": iso(row.get("ended_at")),
        "ended_reason": row.get("ended_reason"),
        "price": decimal_text(row.get("canonical_candidate_midpoint")),
        "lower_bound": decimal_text(row.get("canonical_candidate_lower")),
        "upper_bound": decimal_text(row.get("canonical_candidate_upper")),
        "structural_location": row.get("canonical_structural_location"),
        "supporting_observation_count": row.get(
            "canonical_supporting_observation_count"
        ),
        "supporting_observation_ids": list(
            row.get("canonical_supporting_observation_ids") or []
        ),
    }


def _mrz_lifecycles(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _utc(row["occurred_at"]),
            int(row.get("sequence") or 0),
            str(row["event_key"]),
        ),
    )
    lifecycles: list[dict[str, Any]] = []
    for index, row in enumerate(ordered):
        if str(row["event_type"]) not in {"MRZ_ACTIVATED", "MRZ_MIGRATED"}:
            continue
        next_row = next(
            (
                candidate
                for candidate in ordered[index + 1 :]
                if str(candidate["event_type"]) in {"MRZ_ACTIVATED", "MRZ_MIGRATED"}
            ),
            None,
        )
        lower = Decimal(row["new_core_mrz_lower"])
        upper = Decimal(row["new_core_mrz_upper"])
        tick = Decimal(row.get("instrument_tick") or "0")
        width = max(upper - lower, tick)
        lifecycles.append(
            {
                "source_tracker": "MRZ",
                "event_type": str(row["event_type"]),
                "canonical_event_id": str(row["event_key"]),
                "trigger_event_id": str(row["trigger_event_id"]),
                "symbol": str(row["symbol"]),
                "route": str(row["route_owner"]),
                "sequence": int(row["sequence"]),
                "effective_at": iso(row["occurred_at"]),
                "known_at": iso(row["trigger_received_at"]),
                "ended_effective_at": iso(next_row["occurred_at"]) if next_row else None,
                "ended_known_at": iso(next_row["trigger_received_at"]) if next_row else None,
                "price": decimal_text(row["new_core_mrz_midpoint"]),
                "lower_bound": decimal_text(lower),
                "upper_bound": decimal_text(upper),
                "lower_migration_boundary": decimal_text(lower - Decimal("2") * width),
                "upper_migration_boundary": decimal_text(upper + Decimal("2") * width),
                "structural_location": str(row["structural_location"]),
                "activation_source": str(
                    row.get("activation_source") or "PRODUCTION_QUALIFIED"
                ),
                "confirming_observation_count": int(
                    row.get("confirming_observation_count") or 0
                ),
                "supporting_observation_count": int(
                    row.get("new_supporting_observation_count")
                    or row.get("confirming_observation_count")
                    or 0
                ),
            }
        )
    return lifecycles


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _lifecycle_for_observation(
    lifecycles: Sequence[Mapping[str, Any]], observation: Observation
) -> Mapping[str, Any] | None:
    effective = _utc(observation.observed_at)
    known = _utc(observation.received_at)
    eligible = [
        lifecycle
        for lifecycle in lifecycles
        if _parse_iso(str(lifecycle["effective_at"])) < effective
        and _parse_iso(str(lifecycle["known_at"])) <= known
    ]
    return eligible[-1] if eligible else None


def _pressure_events(
    observations: Sequence[Observation],
    lifecycles: Sequence[Mapping[str, Any]],
    as_known_at: datetime,
) -> list[dict[str, Any]]:
    qualifying: list[tuple[Observation, Mapping[str, Any], str]] = []
    for observation in observations:
        if _utc(observation.received_at) > as_known_at:
            continue
        lifecycle = _lifecycle_for_observation(lifecycles, observation)
        if lifecycle is None:
            continue
        if _parse_iso(str(lifecycle["known_at"])) > _utc(observation.received_at):
            continue
        price = observation.observation_price
        direction = None
        if price > Decimal(str(lifecycle["upper_migration_boundary"])):
            direction = "UP"
        elif price < Decimal(str(lifecycle["lower_migration_boundary"])):
            direction = "DOWN"
        if direction is not None:
            qualifying.append((observation, lifecycle, direction))

    result: list[dict[str, Any]] = []
    known_order = sorted(
        qualifying,
        key=lambda item: (
            _utc(item[0].received_at),
            _utc(item[0].observed_at),
            item[0].id,
        ),
    )
    seen: list[tuple[Observation, Mapping[str, Any], str]] = []
    for observation, lifecycle, direction in known_order:
        seen.append((observation, lifecycle, direction))
        same_lifecycle = [
            item
            for item in seen
            if item[1]["canonical_event_id"] == lifecycle["canonical_event_id"]
        ]
        canonical_order = sorted(same_lifecycle, key=lambda item: item[0].order_key)
        state = classify_current_pressure_directions(
            tuple(item[2] for item in canonical_order)
        )
        recent = canonical_order[-4:]
        result.append(
            {
                "source_tracker": "PRESSURE",
                "event_type": "PRESSURE_HIGHER" if direction == "UP" else "PRESSURE_LOWER",
                "canonical_event_id": observation.event_id,
                "symbol": observation.symbol,
                "route": observation.route.value,
                "observation_type": observation.observation_type.value,
                "effective_at": iso(observation.observed_at),
                "known_at": iso(observation.received_at),
                "price": decimal_text(observation.observation_price),
                "direction": "HIGHER" if direction == "UP" else "LOWER",
                "mrz_lifecycle_event_id": lifecycle["canonical_event_id"],
                "mrz_route": lifecycle["route"],
                "lower_bound": lifecycle["lower_bound"],
                "upper_bound": lifecycle["upper_bound"],
                "lower_migration_boundary": lifecycle["lower_migration_boundary"],
                "upper_migration_boundary": lifecycle["upper_migration_boundary"],
                "current_pressure_state": state.direction,
                "current_pressure_label": state.direction_label,
                "recent_pressure_observation_count": len(recent),
                "recent_higher_observation_count": sum(
                    item[2] == "UP" for item in recent
                ),
                "recent_lower_observation_count": sum(
                    item[2] == "DOWN" for item in recent
                ),
                "state_basis": "RECONSTRUCTED_AS_KNOWN_AT",
            }
        )
    return sorted(
        result,
        key=lambda item: (
            _parse_iso(item["effective_at"]),
            _parse_iso(item["known_at"]),
            item["canonical_event_id"],
        ),
    )


def _filter_known(
    events: Iterable[Mapping[str, Any]], as_known_at: datetime
) -> list[dict[str, Any]]:
    return [
        dict(event)
        for event in events
        if event.get("known_at")
        and _parse_iso(str(event["known_at"])) <= as_known_at
    ]


def _state_history(
    route: str,
    observations: Sequence[Mapping[str, Any]],
    near_misses: Sequence[Mapping[str, Any]],
    lifecycles: Sequence[Mapping[str, Any]],
    pressure: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    def add(state: str, event: Mapping[str, Any], reason: str) -> None:
        changes.append(
            {
                "state": state,
                "label": STATE_LABELS[state],
                "effective_at": event["effective_at"],
                "known_at": event["known_at"],
                "canonical_event_id": event["canonical_event_id"],
                "reason": reason,
            }
        )

    if observations:
        add(
            "CONTEXT_OBSERVED",
            observations[0],
            f"First observed {route} route/IPDA context.",
        )
    for event in near_misses:
        if event["route"] == route:
            add("NEAR_MISS", event, f"Canonical {route} Near Miss recorded.")
    for lifecycle in lifecycles:
        if lifecycle["route"] == route:
            add(
                "STRUCTURE_ESTABLISHED",
                lifecycle,
                f"Authoritative {route} MRZ lifecycle established.",
            )
    previous = "NEUTRAL"
    for event in pressure:
        if event["mrz_route"] != route:
            continue
        current = str(event["current_pressure_state"])
        if current != "NEUTRAL" and current != previous:
            add(
                "REASSESSMENT",
                event,
                f"Latest-four Current Pressure changed to {event['current_pressure_label']}.",
            )
        previous = current
    changes.sort(
        key=lambda item: (
            _parse_iso(item["known_at"]),
            _parse_iso(item["effective_at"]),
            item["canonical_event_id"],
        )
    )
    deduplicated: list[dict[str, Any]] = []
    for change in changes:
        if deduplicated and change["state"] == deduplicated[-1]["state"]:
            continue
        deduplicated.append(change)
    return deduplicated


def _next_condition(
    route: str,
    state: str,
    latest_pressure: Mapping[str, Any] | None,
) -> str:
    if state == "CONTEXT_OBSERVED":
        return (
            f"Watch for a canonical {route} Near Miss or MRZ activation; "
            "no observation-count threshold is inferred in Phase 1."
        )
    if state == "NEAR_MISS":
        return f"Watch for authoritative {route} MRZ activation or the candidate episode ending."
    if state == "STRUCTURE_ESTABLISHED":
        if latest_pressure and latest_pressure["current_pressure_state"] == "NEUTRAL":
            return "Watch the next qualifying observation for a latest-four Current Pressure change."
        return "Watch for a canonical MRZ migration, route change, new Near Miss, or Current Pressure change."
    if state == "REASSESSMENT":
        return "Watch for new structural development: MRZ migration/route change, Near Miss, or a Current Pressure change."
    return "No execution condition is defined; inspect new canonical evidence as it arrives."


def build_symbol_opportunity(
    inputs: Mapping[str, Any],
    symbol: str,
    *,
    as_known_at: datetime | None = None,
) -> dict[str, Any] | None:
    normalized = symbol.upper()
    snapshot_at = _utc(inputs["as_of"])
    cursor = _as_known_at(as_known_at, snapshot_at)
    source_observations = [
        observation
        for observation in inputs.get("observations", ())
        if observation.symbol == normalized and _utc(observation.received_at) <= cursor
    ]
    source_observations.sort(key=lambda item: item.order_key)
    if not source_observations:
        return None
    observation_events = [_observation_event(item) for item in source_observations]
    mrz_rows = [
        row for row in inputs.get("mrz_events", ()) if str(row["symbol"]) == normalized
    ]
    all_lifecycles = _mrz_lifecycles(mrz_rows)
    lifecycles = _filter_known(all_lifecycles, cursor)
    for lifecycle in lifecycles:
        if (
            lifecycle.get("ended_known_at")
            and _parse_iso(str(lifecycle["ended_known_at"])) > cursor
        ):
            lifecycle["ended_effective_at"] = None
            lifecycle["ended_known_at"] = None
    near_misses = [
        event
        for event in (
            _near_miss_event(row)
            for row in inputs.get("near_miss_episodes", ())
            if str(row["symbol"]) == normalized
        )
        if event is not None and _parse_iso(event["known_at"]) <= cursor
    ]
    pressure = _pressure_events(source_observations, all_lifecycles, cursor)
    persisted_pressure = [
        {
            "canonical_event_id": str(row["event_key"]),
            "effective_at": iso(row["supporting_observed_at"] or row["occurred_at"]),
            "known_at": iso(row["occurred_at"]),
            "previous_state": str(row["previous_state"]),
            "current_state": str(row["current_state"]),
        }
        for row in inputs.get("current_pressure_events", ())
        if str(row["symbol"]) == normalized and _utc(row["occurred_at"]) <= cursor
    ]

    episodes = []
    for route in (Route.BTD.value, Route.STR.value):
        route_observations = [
            event for event in observation_events if event["route"] == route
        ]
        if not route_observations:
            continue
        opposing = [
            event for event in observation_events if event["route"] != route
        ]
        route_near = [event for event in near_misses if event["route"] == route]
        opposing_near = [event for event in near_misses if event["route"] != route]
        route_lifecycles = [event for event in lifecycles if event["route"] == route]
        route_pressure = [event for event in pressure if event["mrz_route"] == route]
        history = _state_history(
            route,
            route_observations,
            near_misses,
            lifecycles,
            pressure,
        )
        state = history[-1]["state"] if history else "CONTEXT_OBSERVED"
        latest_evidence = max(
            [*route_observations, *route_near, *route_lifecycles, *route_pressure],
            key=lambda item: (
                _parse_iso(item["known_at"]),
                _parse_iso(item["effective_at"]),
                item["canonical_event_id"],
            ),
        )
        evidence = []
        for index, event in enumerate(
            sorted(
                [
                    *route_observations,
                    *opposing,
                    *route_near,
                    *opposing_near,
                    *route_lifecycles,
                    *route_pressure,
                ],
                key=lambda item: (
                    _parse_iso(item["effective_at"]),
                    _parse_iso(item["known_at"]),
                    item["canonical_event_id"],
                ),
            ),
            1,
        ):
            item = dict(event)
            if event in opposing or event in opposing_near:
                relationship = "CONFLICTING_EVIDENCE"
            elif event.get("source_tracker") in {"MRZ", "NEAR_MISS"}:
                relationship = "STRUCTURAL_DEVELOPMENT"
            elif event.get("source_tracker") == "PRESSURE":
                relationship = "HISTORICAL_OUTCOME_EVIDENCE"
            elif event is route_observations[0]:
                relationship = "CONTEXT"
            else:
                relationship = "SUPPORTING_EVIDENCE"
            item.update({"relationship": relationship, "sequence_order": index})
            evidence.append(item)
        latest_pressure = route_pressure[-1] if route_pressure else None
        episodes.append(
            {
                "episode_id": _episode_id(
                    normalized, route, route_observations[0]["canonical_event_id"]
                ),
                "symbol": normalized,
                "hypothesis": route,
                "origin_event_id": route_observations[0]["canonical_event_id"],
                "origin_effective_at": route_observations[0]["effective_at"],
                "first_known_at": route_observations[0]["known_at"],
                "state": state,
                "state_label": STATE_LABELS[state],
                "state_history": history,
                "associated_mrz_lifecycle_ids": [
                    item["canonical_event_id"] for item in route_lifecycles
                ],
                "latest_relevant_event": latest_evidence,
                "supporting_evidence_count": sum(
                    item["relationship"] == "SUPPORTING_EVIDENCE"
                    for item in evidence
                ),
                "conflicting_evidence_count": sum(
                    item["relationship"] == "CONFLICTING_EVIDENCE"
                    for item in evidence
                ),
                "evidence": evidence,
                "next_observable_condition": _next_condition(
                    route, state, latest_pressure
                ),
                "entry_verification": {
                    "status": "NOT_VERIFIED",
                    "label": "Entry not verified",
                    "reason": "Phase 1 reconstructs research evidence only; execution readiness is not established.",
                },
                "rule_version": RULE_VERSION,
                "replay": {
                    "as_known_at": iso(cursor),
                    "effective_time_preserved": True,
                    "knowledge_time_preserved": True,
                    "deterministic": True,
                },
            }
        )

    episodes.sort(
        key=lambda item: (
            -STATE_RANK[item["state"]],
            item["first_known_at"],
            item["hypothesis"],
        )
    )
    latest_episode = episodes[0]
    latest_location = observation_events[-1].get("ipda_location_label")
    assessment = {
        "what_happened": (
            f"{len(observation_events)} canonical route/IPDA observations, "
            f"{len(near_misses)} Near Miss episode(s), and {len(lifecycles)} "
            "authoritative MRZ lifecycle event(s) are available at this replay cursor."
        ),
        "what_changed": (
            f"Latest material evidence: {latest_episode['latest_relevant_event']['event_type']} "
            f"known at {latest_episode['latest_relevant_event']['known_at']}."
        ),
        "conflicting_evidence": (
            f"Both BTD and STR hypotheses remain visible ({sum(item['hypothesis'] == 'BTD' for item in episodes)} BTD, "
            f"{sum(item['hypothesis'] == 'STR' for item in episodes)} STR); opposing route evidence is never erased."
            if len(episodes) > 1
            else "No opposite-route hypothesis is present in the evidence available at this cursor."
        ),
        "next_condition": latest_episode["next_observable_condition"],
        "entry_verified": False,
        "entry_message": "Not verified. Phase 1 is historical opportunity research, not an execution signal.",
    }
    return {
        "schema_version": "opportunity-intelligence.phase1",
        "symbol": normalized,
        "as_of": iso(snapshot_at),
        "as_known_at": iso(cursor),
        "latest_ipda_location": latest_location,
        "episodes": episodes,
        "selected_episode_id": latest_episode["episode_id"],
        "observations": observation_events,
        "near_miss_events": near_misses,
        "mrz_lifecycles": lifecycles,
        "pressure_observations": pressure,
        "persisted_current_pressure_events": persisted_pressure,
        "current_pressure_persistence_note": (
            "Reconstructed historical latest-four states are labelled separately from "
            "contemporaneously persisted Current Pressure events."
        ),
        "ote": {
            "status": "not_connected",
            "source": "EDGE_BOT",
            "message": "OTE feed not connected (planned); no OTE price markers are shown.",
        },
        "assessment": assessment,
    }


def _candidate_summary(detail: Mapping[str, Any]) -> dict[str, Any]:
    episode = detail["episodes"][0]
    mrz = next(
        (
            item
            for item in reversed(detail["mrz_lifecycles"])
            if item["route"] == episode["hypothesis"]
        ),
        None,
    )
    latest_pressure = next(
        (
            item
            for item in reversed(detail["pressure_observations"])
            if item["mrz_route"] == episode["hypothesis"]
        ),
        None,
    )
    return {
        "symbol": detail["symbol"],
        "episode_id": episode["episode_id"],
        "hypothesis": episode["hypothesis"],
        "state": episode["state"],
        "state_label": episode["state_label"],
        "origin_event_id": episode["origin_event_id"],
        "origin_effective_at": episode["origin_effective_at"],
        "first_known_at": episode["first_known_at"],
        "latest_event_at": episode["latest_relevant_event"]["effective_at"],
        "latest_known_at": episode["latest_relevant_event"]["known_at"],
        "latest_event_type": episode["latest_relevant_event"]["event_type"],
        "ipda_location": detail["latest_ipda_location"],
        "mrz": (
            {
                "lower": mrz["lower_bound"],
                "upper": mrz["upper_bound"],
                "route": mrz["route"],
                "known_at": mrz["known_at"],
            }
            if mrz
            else None
        ),
        "current_pressure": (
            {
                "state": latest_pressure["current_pressure_state"],
                "label": latest_pressure["current_pressure_label"],
                "higher": latest_pressure["recent_higher_observation_count"],
                "lower": latest_pressure["recent_lower_observation_count"],
                "count": latest_pressure["recent_pressure_observation_count"],
                "basis": latest_pressure["state_basis"],
            }
            if latest_pressure
            else {
                "state": "NEUTRAL",
                "label": "Neutral",
                "higher": 0,
                "lower": 0,
                "count": 0,
                "basis": "RECONSTRUCTED_AS_KNOWN_AT",
            }
        ),
        "conflicting_evidence_count": episode["conflicting_evidence_count"],
        "next_observable_condition": episode["next_observable_condition"],
        "entry_verified": False,
    }


def build_opportunity_overview(
    inputs: Mapping[str, Any],
    *,
    group_id: int | None = None,
    as_known_at: datetime | None = None,
) -> dict[str, Any]:
    groups = list(inputs.get("groups", ()))
    if group_id is not None:
        groups = [group for group in groups if int(group["id"]) == group_id]
    requested_symbols = sorted(
        {
            str(symbol)
            for group in groups
            for symbol in group.get("members", ())
        }
    )
    if not groups:
        requested_symbols = sorted(
            {observation.symbol for observation in inputs.get("observations", ())}
        )
    details = {
        symbol: detail
        for symbol in requested_symbols
        if (detail := build_symbol_opportunity(
            inputs, symbol, as_known_at=as_known_at
        ))
        is not None
    }
    candidates = [_candidate_summary(detail) for detail in details.values()]
    candidates.sort(
        key=lambda item: (
            -STATE_RANK[item["state"]],
            -_parse_iso(item["latest_known_at"]).timestamp(),
            item["symbol"],
        )
    )
    group_summaries = []
    for group in groups:
        members = {str(item) for item in group.get("members", ())}
        group_candidates = [
            candidate for candidate in candidates if candidate["symbol"] in members
        ]
        group_summaries.append(
            {
                "id": int(group["id"]),
                "name": str(group["name"]),
                "member_count": len(members),
                "candidate_symbol_count": len(
                    {item["symbol"] for item in group_candidates}
                ),
                "context_or_developing_count": len(
                    {
                        item["symbol"]
                        for item in group_candidates
                        if item["state"] in {"CONTEXT_OBSERVED", "DEVELOPING"}
                    }
                ),
                "near_miss_count": len(
                    {
                        item["symbol"]
                        for item in group_candidates
                        if item["state"] == "NEAR_MISS"
                    }
                ),
                "structure_established_count": len(
                    {
                        item["symbol"]
                        for item in group_candidates
                        if item["state"] == "STRUCTURE_ESTABLISHED"
                    }
                ),
                "reassessment_count": len(
                    {
                        item["symbol"]
                        for item in group_candidates
                        if item["state"] == "REASSESSMENT"
                    }
                ),
                "earliest_candidate": min(
                    group_candidates,
                    key=lambda item: (
                        item["first_known_at"], item["symbol"]
                    ),
                    default=None,
                ),
                "latest_material_event": max(
                    group_candidates,
                    key=lambda item: (
                        item["latest_known_at"], item["symbol"]
                    ),
                    default=None,
                ),
                "candidates": group_candidates,
            }
        )
    unique_candidates = {item["symbol"]: item for item in candidates}
    return {
        "schema_version": "opportunity-intelligence.phase1",
        "as_of": iso(_utc(inputs["as_of"])),
        "as_known_at": iso(
            _as_known_at(as_known_at, _utc(inputs["as_of"]))
        ),
        "mode": "RESEARCH_SHADOW",
        "rule_version": RULE_VERSION,
        "counts": {
            "candidate_symbols": len(unique_candidates),
            "context_or_developing": sum(
                item["state"] in {"CONTEXT_OBSERVED", "DEVELOPING"}
                for item in unique_candidates.values()
            ),
            "near_miss": sum(
                item["state"] == "NEAR_MISS"
                for item in unique_candidates.values()
            ),
            "structure_established": sum(
                item["state"] == "STRUCTURE_ESTABLISHED"
                for item in unique_candidates.values()
            ),
            "needs_reassessment": sum(
                item["state"] == "REASSESSMENT"
                for item in unique_candidates.values()
            ),
        },
        "groups": group_summaries,
        "candidates": candidates,
        "cross_group_note": (
            "Counts deduplicate symbols within each group. A symbol in multiple groups "
            "appears in each relevant group but once in universe totals."
        ),
        "detection_note": (
            "Context Observed is not automatically upgraded to Developing by an "
            "invented observation-count threshold. Near Miss and Structure Established "
            "come only from canonical events."
        ),
        "ote": {
            "status": "not_connected",
            "message": "OTE feed not connected (planned).",
        },
    }
