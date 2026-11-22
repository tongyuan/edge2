from __future__ import annotations

"""Authoritative, replay-safe structural interpretation of canonical MRZ history.

This module never forms or mutates an MRZ. It interprets already-canonical MRZ
states using instrument precision, event time and first-known time. The same
result is consumed by group, symbol, opportunity-map and notification surfaces.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping, Sequence


DETECTOR_VERSION = "SI-1.0.0"
SCHEMA_VERSION = "structural-intelligence.v1"


@dataclass(frozen=True)
class MRZState:
    event_key: str
    sequence: int
    symbol: str
    route: str
    occurred_at: datetime
    first_known_at: datetime
    lower: Decimal
    upper: Decimal
    midpoint: Decimal
    tick: Decimal


def _time(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid canonical decimal: {value!r}") from exc


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def _value(row: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return None


def canonical_states(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_known_at: datetime | str | None = None,
) -> list[MRZState]:
    """Normalize canonical activation/migration states at an as-known cutoff."""
    cutoff = _time(as_known_at) if as_known_at is not None else None
    states: list[MRZState] = []
    seen: set[str] = set()
    for row in rows:
        if str(row.get("event_type", "")) not in {"MRZ_ACTIVATED", "MRZ_MIGRATED"}:
            continue
        event_key = str(row.get("event_key") or "")
        if not event_key or event_key in seen:
            continue
        occurred_at = _time(row["occurred_at"])
        first_known_at = _time(
            _value(row, "first_known_at", "created_at", "received_at")
            or occurred_at
        )
        if cutoff and (occurred_at > cutoff or first_known_at > cutoff):
            continue
        lower = _decimal(_value(row, "new_core_mrz_lower", "lower", "to_lower"))
        upper = _decimal(_value(row, "new_core_mrz_upper", "upper", "to_upper"))
        midpoint_value = _value(row, "new_core_mrz_midpoint", "midpoint")
        midpoint = _decimal(midpoint_value) if midpoint_value is not None else (lower + upper) / 2
        tick_value = _value(row, "instrument_tick", "observation_price_tick")
        tick = abs(_decimal(tick_value)) if tick_value is not None else Decimal("0.00000001")
        if upper < lower or tick <= 0:
            continue
        states.append(
            MRZState(
                event_key=event_key,
                sequence=int(row["sequence"]),
                symbol=str(row["symbol"]),
                route=str(_value(row, "route_owner", "route") or ""),
                occurred_at=occurred_at,
                first_known_at=first_known_at,
                lower=lower,
                upper=upper,
                midpoint=midpoint,
                tick=tick,
            )
        )
        seen.add(event_key)
    states.sort(key=lambda state: (state.occurred_at, state.first_known_at, state.sequence, state.event_key))
    return states


def _compare(left: Decimal, right: Decimal, tick: Decimal) -> int:
    tolerance = max(tick / 2, Decimal("0.000000000001"))
    difference = left - right
    if abs(difference) <= tolerance:
        return 0
    return 1 if difference > 0 else -1


def _development_id(symbol: str, kind: str, maturity: str, event_key: str) -> str:
    identity = f"{DETECTOR_VERSION}|{symbol}|{kind}|{maturity}|{event_key}"
    return "SD:" + sha256(identity.encode("utf-8")).hexdigest()[:24]


def _pivot_payload(
    *,
    state: MRZState,
    kind: str,
    maturity: str,
    supporting: Sequence[MRZState],
    confirmation: MRZState | None,
) -> dict[str, Any]:
    return {
        "development_id": _development_id(state.symbol, kind, maturity, state.event_key),
        "type": kind,
        "maturity": maturity,
        "pivot_event_key": state.event_key,
        "migration_sequence": state.sequence,
        "route": state.route,
        "lower": format(state.lower, "f"),
        "upper": format(state.upper, "f"),
        "midpoint": format(state.midpoint, "f"),
        "event_time": _iso(state.occurred_at),
        "first_known_time": _iso(state.first_known_at),
        "confirmation_time": _iso(confirmation.first_known_at) if confirmation else None,
        "supporting_event_ids": [item.event_key for item in supporting],
        "detector_version": DETECTOR_VERSION,
    }


def _confirmed_pivots(states: Sequence[MRZState]) -> list[dict[str, Any]]:
    pivots: list[dict[str, Any]] = []
    previous_high: MRZState | None = None
    previous_low: MRZState | None = None
    for index in range(1, len(states) - 1):
        before, current, after = states[index - 1 : index + 2]
        tick = max(before.tick, current.tick, after.tick)
        incoming = _compare(current.midpoint, before.midpoint, tick)
        outgoing = _compare(after.midpoint, current.midpoint, tick)
        if incoming > 0 and outgoing < 0:
            label = "HIGH" if previous_high is None else ("HH" if _compare(current.midpoint, previous_high.midpoint, tick) > 0 else "LH" if _compare(current.midpoint, previous_high.midpoint, tick) < 0 else "EH")
            pivots.append(_pivot_payload(state=current, kind=label, maturity="confirmed", supporting=(before, current, after), confirmation=after))
            previous_high = current
        elif incoming < 0 and outgoing > 0:
            label = "LOW" if previous_low is None else ("HL" if _compare(current.midpoint, previous_low.midpoint, tick) > 0 else "LL" if _compare(current.midpoint, previous_low.midpoint, tick) < 0 else "EL")
            pivots.append(_pivot_payload(state=current, kind=label, maturity="confirmed", supporting=(before, current, after), confirmation=after))
            previous_low = current
    return pivots


def _latest_developing_pivot(states: Sequence[MRZState], pivots: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if len(states) < 3:
        return None
    latest = states[-1]
    previous = states[-2]
    tick = max(latest.tick, previous.tick)
    movement = _compare(latest.midpoint, previous.midpoint, tick)
    if movement == 0:
        return None
    last_high = next((item for item in reversed(pivots) if item["type"] in {"HIGH", "HH", "LH", "EH"}), None)
    last_low = next((item for item in reversed(pivots) if item["type"] in {"LOW", "HL", "LL", "EL"}), None)
    if movement < 0 and last_low and last_high and int(last_high["migration_sequence"]) > int(last_low["migration_sequence"]):
        comparison = _compare(latest.midpoint, _decimal(last_low["midpoint"]), tick)
        if comparison > 0:
            return _pivot_payload(state=latest, kind="HL", maturity="developing", supporting=(previous, latest), confirmation=None)
    if movement > 0 and last_high and last_low and int(last_low["migration_sequence"]) > int(last_high["migration_sequence"]):
        comparison = _compare(latest.midpoint, _decimal(last_high["midpoint"]), tick)
        if comparison < 0:
            return _pivot_payload(state=latest, kind="LH", maturity="developing", supporting=(previous, latest), confirmation=None)
    return None


def _meaningful_extension(states: Sequence[MRZState], pivots: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if len(states) < 4:
        return None
    latest = states[-1]
    recent = states[-3:]
    signs = [_compare(recent[index].midpoint, recent[index - 1].midpoint, max(recent[index].tick, recent[index - 1].tick)) for index in (1, 2)]
    if signs == [1, 1]:
        last_high = next((item for item in reversed(pivots) if item["type"] in {"HIGH", "HH", "LH", "EH"}), None)
        if last_high and _compare(latest.midpoint, _decimal(last_high["midpoint"]), latest.tick) > 0:
            return _pivot_payload(state=latest, kind="HH", maturity="confirmed", supporting=recent, confirmation=latest)
    if signs == [-1, -1]:
        last_low = next((item for item in reversed(pivots) if item["type"] in {"LOW", "HL", "LL", "EL"}), None)
        if last_low and _compare(latest.midpoint, _decimal(last_low["midpoint"]), latest.tick) < 0:
            return _pivot_payload(state=latest, kind="LL", maturity="confirmed", supporting=recent, confirmation=latest)
    return None


def _directional_structure(states: Sequence[MRZState], pivots: Sequence[Mapping[str, Any]]) -> str:
    if len(states) < 4:
        return "undetermined"
    recent_signs = [
        _compare(states[index].midpoint, states[index - 1].midpoint, max(states[index].tick, states[index - 1].tick))
        for index in range(max(1, len(states) - 3), len(states))
    ]
    if len(recent_signs) == 3 and all(sign > 0 for sign in recent_signs):
        return "ascending"
    if len(recent_signs) == 3 and all(sign < 0 for sign in recent_signs):
        return "descending"
    recent_types = [str(item["type"]) for item in pivots if item["type"] not in {"HIGH", "LOW", "EH", "EL"}][-4:]
    upward = {"HH", "HL"}
    downward = {"LH", "LL"}
    if "HH" in recent_types and "HL" in recent_types and not set(recent_types[-2:]) & downward:
        return "ascending"
    if "LH" in recent_types and "LL" in recent_types and not set(recent_types[-2:]) & upward:
        return "descending"
    if recent_types or any(sign != 0 for sign in recent_signs):
        return "transitional"
    return "undetermined"


def classify_structural_history(
    rows: Sequence[Mapping[str, Any]],
    *,
    as_known_at: datetime | str | None = None,
) -> dict[str, Any]:
    states = canonical_states(rows, as_known_at=as_known_at)
    symbol = states[0].symbol if states else ""
    pivots = _confirmed_pivots(states)
    structure = _directional_structure(states, pivots)
    developing = _latest_developing_pivot(states, pivots)
    extension = _meaningful_extension(states, pivots)
    latest_development = developing or extension or (pivots[-1] if pivots else None)
    if developing and structure in {"ascending", "descending"}:
        structure = "transitional"

    last_established = _directional_structure(states[:-1], _confirmed_pivots(states[:-1])) if len(states) > 4 else "undetermined"
    if structure == "ascending":
        hypothesis = "BTD_DOMINANT"
    elif structure == "descending":
        hypothesis = "STR_DOMINANT"
    elif structure == "transitional" and (developing or latest_development):
        kind = str((developing or latest_development or {}).get("type", ""))
        if last_established == "descending" and kind in {"HL", "HH"}:
            hypothesis = "STR_DOMINANT_EMERGING_BTD"
        elif last_established == "ascending" and kind in {"LH", "LL"}:
            hypothesis = "BTD_DOMINANT_EMERGING_STR"
        else:
            hypothesis = "UNRESOLVED"
    elif not states:
        hypothesis = "INSUFFICIENT_HISTORY"
    else:
        hypothesis = "UNRESOLVED"

    hypothesis_labels = {
        "STR_DOMINANT": "STR dominant",
        "STR_DOMINANT_EMERGING_BTD": "STR dominant with emerging BTD evidence",
        "BTD_DOMINANT": "BTD dominant",
        "BTD_DOMINANT_EMERGING_STR": "BTD dominant with emerging STR evidence",
        "UNRESOLVED": "Unresolved",
        "INSUFFICIENT_HISTORY": "Insufficient history",
    }
    evidence_state = (
        "developing" if latest_development and latest_development["maturity"] == "developing"
        else "established" if structure in {"ascending", "descending"}
        else "insufficient" if structure == "undetermined"
        else "mixed"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "detector_version": DETECTOR_VERSION,
        "symbol": symbol,
        "as_known_at": _iso(_time(as_known_at)) if as_known_at is not None else (_iso(states[-1].first_known_at) if states else None),
        "history_state_count": len(states),
        "migration_structure": structure,
        "migration_structure_label": structure.title(),
        "route_hypothesis": hypothesis,
        "route_hypothesis_label": hypothesis_labels[hypothesis],
        "evidence_state": evidence_state,
        "latest_development": latest_development,
        "pivots": pivots,
        "recent_sequence": [item["type"] for item in pivots[-4:]],
        "states": [
            {
                "event_key": state.event_key,
                "sequence": state.sequence,
                "route": state.route,
                "lower": format(state.lower, "f"),
                "upper": format(state.upper, "f"),
                "midpoint": format(state.midpoint, "f"),
                "event_time": _iso(state.occurred_at),
                "first_known_time": _iso(state.first_known_at),
            }
            for state in states
        ],
        "classification_basis": "canonical_mrz_history_as_known_at_instrument_precision",
    }


def meaningful_development(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a notification-eligible change, never an ordinary migration."""
    development = current.get("latest_development")
    if not isinstance(development, Mapping):
        return None
    previous_id = (previous or {}).get("latest_development", {}).get("development_id") if isinstance((previous or {}).get("latest_development"), Mapping) else None
    if development.get("development_id") == previous_id:
        return None
    kind = str(development.get("type", ""))
    maturity = str(development.get("maturity", ""))
    if kind not in {"HL", "LH", "HH", "LL"} or maturity not in {"developing", "confirmed"}:
        return None
    return dict(development)
