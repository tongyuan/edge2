from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Mapping, Sequence

from app.validation import normalize_symbol


TradeDeskAuthorityInputProvider = Callable[[], Sequence[Mapping[str, object]]]


class TradeDeskAuthorityInconsistent(RuntimeError):
    """Raised when persisted authority and its immutable event lineage disagree."""


def _fail(symbol: str, reason: str) -> TradeDeskAuthorityInconsistent:
    return TradeDeskAuthorityInconsistent(f"{symbol}: {reason}")


def _decimal(row: Mapping[str, object], key: str, symbol: str) -> Decimal:
    value = row.get(key)
    try:
        decimal = Decimal(value)  # type: ignore[arg-type]
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise _fail(symbol, f"{key} is not a valid decimal") from exc
    if not decimal.is_finite():
        raise _fail(symbol, f"{key} is not finite")
    return decimal


def _timestamp(row: Mapping[str, object], key: str, symbol: str) -> datetime:
    value = row.get(key)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _fail(symbol, f"{key} is not timezone-aware")
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _range(
    row: Mapping[str, object],
    lower_key: str,
    upper_key: str,
    midpoint_key: str,
    symbol: str,
) -> tuple[Decimal, Decimal, Decimal]:
    lower = _decimal(row, lower_key, symbol)
    upper = _decimal(row, upper_key, symbol)
    midpoint = _decimal(row, midpoint_key, symbol)
    if upper <= lower:
        raise _fail(symbol, f"{upper_key} must be greater than {lower_key}")
    if midpoint != (lower + upper) / Decimal("2"):
        raise _fail(symbol, f"{midpoint_key} does not match the MRZ bounds")
    return lower, upper, midpoint


def _identifier(row: Mapping[str, object], key: str, symbol: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise _fail(symbol, f"{key} is missing")
    return value


class TradeDeskAuthorityService:
    """Build the minimal TradeDesk snapshot from persisted EDGE authority lineage."""

    def __init__(
        self,
        input_provider: TradeDeskAuthorityInputProvider,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._input_provider = input_provider
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def generate_report(self) -> dict[str, object]:
        symbols: list[dict[str, object]] = []
        seen: set[str] = set()
        for row in self._input_provider():
            symbol = str(row.get("symbol") or "")
            try:
                canonical_symbol = normalize_symbol(symbol)
            except ValueError as exc:
                raise _fail(symbol or "<missing>", "symbol is not canonical") from exc
            if canonical_symbol != symbol:
                raise _fail(symbol, "symbol is not canonical")
            if symbol in seen:
                raise _fail(symbol, "duplicate authoritative symbol")
            seen.add(symbol)
            symbols.append(self._symbol_payload(row, symbol))

        generated_at = self._clock()
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise TradeDeskAuthorityInconsistent("generated_at is not timezone-aware")
        return {
            "schema_version": 1,
            "generated_at": _iso_utc(generated_at),
            "symbols": sorted(symbols, key=lambda item: str(item["symbol"])),
        }

    @staticmethod
    def _symbol_payload(
        row: Mapping[str, object],
        symbol: str,
    ) -> dict[str, object]:
        current_lower, current_upper, current_midpoint = _range(
            row,
            "current_lower",
            "current_upper",
            "current_midpoint",
            symbol,
        )
        current_activated_at = _timestamp(
            row,
            "current_activated_at",
            symbol,
        )
        current_activation_event_id = _identifier(
            row,
            "current_activation_event_id",
            symbol,
        )
        current_route_owner = _identifier(row, "current_route_owner", symbol)
        current_activation_source = _identifier(
            row,
            "current_activation_source",
            symbol,
        )

        _identifier(row, "current_authority_event_key", symbol)
        current_event_type = _identifier(row, "current_event_type", symbol)
        current_event_sequence = row.get("current_event_sequence")
        if not isinstance(current_event_sequence, int) or current_event_sequence < 1:
            raise _fail(symbol, "current authority event sequence is invalid")
        if row.get("current_event_symbol") != symbol:
            raise _fail(symbol, "current authority event symbol does not match")
        if row.get("current_trigger_symbol") != symbol:
            raise _fail(symbol, "current activation event belongs to another symbol")
        if row.get("current_event_route_owner") != current_route_owner:
            raise _fail(symbol, "current authority route does not match active_mrz")
        if row.get("current_event_activation_source") != current_activation_source:
            raise _fail(symbol, "current activation source does not match active_mrz")
        if _identifier(row, "current_event_trigger_event_id", symbol) != current_activation_event_id:
            raise _fail(symbol, "current activation event does not match active_mrz")
        if _timestamp(row, "current_event_occurred_at", symbol) != current_activated_at:
            raise _fail(symbol, "current activation timestamp does not match active_mrz")
        event_lower, event_upper, event_midpoint = _range(
            row,
            "current_event_lower",
            "current_event_upper",
            "current_event_midpoint",
            symbol,
        )
        if (
            event_lower != current_lower
            or event_upper != current_upper
            or event_midpoint != current_midpoint
        ):
            raise _fail(symbol, "current authority event MRZ does not match active_mrz")

        previous = None
        if current_event_type == "MRZ_ACTIVATED":
            if (
                current_event_sequence != 1
                or row.get("current_event_previous_route_owner") is not None
                or row.get("current_event_old_lower") is not None
                or row.get("current_event_old_upper") is not None
                or row.get("previous_authority_event_key") is not None
            ):
                raise _fail(symbol, "initial activation contains inconsistent prior authority")
        elif current_event_type == "MRZ_MIGRATED":
            previous = TradeDeskAuthorityService._previous_payload(
                row,
                symbol,
                current_event_sequence,
                current_activated_at,
            )
        else:
            raise _fail(symbol, "latest authority event type is unsupported")

        return {
            "symbol": symbol,
            "current_mrz": {
                "lower": format(current_lower, "f"),
                "upper": format(current_upper, "f"),
                "activated_at": _iso_utc(current_activated_at),
                "activation_event_id": current_activation_event_id,
            },
            "previous_mrz": previous,
        }

    @staticmethod
    def _previous_payload(
        row: Mapping[str, object],
        symbol: str,
        current_event_sequence: int,
        current_activated_at: datetime,
    ) -> dict[str, str]:
        _identifier(row, "previous_authority_event_key", symbol)
        previous_event_type = _identifier(row, "previous_event_type", symbol)
        if previous_event_type not in {"MRZ_ACTIVATED", "MRZ_MIGRATED"}:
            raise _fail(symbol, "previous authority event type is unsupported")
        previous_event_sequence = row.get("previous_event_sequence")
        if (
            not isinstance(previous_event_sequence, int)
            or previous_event_sequence < 1
            or previous_event_sequence >= current_event_sequence
        ):
            raise _fail(symbol, "previous authority event sequence is invalid")
        if row.get("previous_event_symbol") != symbol:
            raise _fail(symbol, "previous authority event symbol does not match")
        if row.get("previous_trigger_symbol") != symbol:
            raise _fail(symbol, "previous activation event belongs to another symbol")

        previous_lower, previous_upper, _previous_midpoint = _range(
            row,
            "previous_lower",
            "previous_upper",
            "previous_midpoint",
            symbol,
        )
        previous_activated_at = _timestamp(
            row,
            "previous_activated_at",
            symbol,
        )
        if previous_activated_at > current_activated_at:
            raise _fail(symbol, "previous authority is newer than current authority")
        previous_route_owner = _identifier(row, "previous_event_route_owner", symbol)
        if row.get("current_event_previous_route_owner") != previous_route_owner:
            raise _fail(symbol, "migration previous route does not match lineage")
        old_lower = _decimal(row, "current_event_old_lower", symbol)
        old_upper = _decimal(row, "current_event_old_upper", symbol)
        if old_lower != previous_lower or old_upper != previous_upper:
            raise _fail(symbol, "migration previous MRZ does not match lineage")

        return {
            "lower": format(previous_lower, "f"),
            "upper": format(previous_upper, "f"),
            "activated_at": _iso_utc(previous_activated_at),
            "activation_event_id": _identifier(
                row,
                "previous_activation_event_id",
                symbol,
            ),
        }
