from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain import ObservationType, Route


SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")


def normalize_symbol(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if ":" in symbol:
        symbol = symbol.rsplit(":", 1)[-1]
    symbol = "".join(symbol.split())
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("symbol must contain only A-Z, 0-9, dot, underscore, or hyphen")
    return symbol


def decimal_tick(value: Decimal) -> Decimal:
    exponent = value.as_tuple().exponent
    return Decimal(1).scaleb(exponent) if exponent < 0 else Decimal(1)


class ObservationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["4.3"]
    event_id: str = Field(min_length=1, max_length=160)
    symbol: str
    route: Route
    observation_type: ObservationType
    observation_price: Decimal
    ipda_20w_high: Decimal
    ipda_20w_low: Decimal
    observed_at: datetime
    webhook_secret: str | None = Field(default=None, exclude=True, max_length=512)

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("event_id must be non-empty printable text")
        return value

    @field_validator("symbol", mode="before")
    @classmethod
    def validate_symbol(cls, value: Any) -> str:
        return normalize_symbol(value)

    @field_validator("observation_price", "ipda_20w_high", "ipda_20w_low")
    @classmethod
    def validate_finite_decimal(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("numeric values must be finite")
        return value

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include an explicit timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_contract(self) -> "ObservationPayload":
        if self.observation_price <= 0:
            raise ValueError("observation_price must be positive")
        if self.ipda_20w_high <= self.ipda_20w_low:
            raise ValueError("ipda_20w_high must be greater than ipda_20w_low")
        expected = ObservationType.RECLAIM if self.route is Route.BTD else ObservationType.REJECTION
        if self.observation_type is not expected:
            raise ValueError(f"{self.route.value} requires observation_type={expected.value}")
        return self

    def price_tick(self, configured_ticks: dict[str, Decimal]) -> Decimal:
        return configured_ticks.get(self.symbol, decimal_tick(self.observation_price))


TRADEDESK_ENTRY_EVENT_TYPES = {
    "ENTRY_TOUCHED",
    "ENTRY_CONFIRMED",
    "ENTRY_INVALIDATED",
    "ENTRY_STOPPED",
    "ENTRY_TARGET_TAKEN",
    "ENTRY_AMBIGUOUS",
    "ENTRY_EXIT_LEVEL_REACHED",
}

TRADEDESK_EXIT_LEVEL_ORDER = (
    "C-MID", "C-2W", "C-1W", "C+1W", "C+2W", "EQM",
    "P-MID", "P-2W", "P-1W", "P+1W", "P+2W",
)
TRADEDESK_EXIT_LEVEL_IDS = set(TRADEDESK_EXIT_LEVEL_ORDER)
TRADEDESK_EXIT_LEVEL_MASK = (1 << len(TRADEDESK_EXIT_LEVEL_ORDER)) - 1


def decode_tradedesk_level_mask(mask: int) -> list[str]:
    if mask < 0 or mask > TRADEDESK_EXIT_LEVEL_MASK:
        raise ValueError("level mask contains unknown canonical identities")
    return [
        level_id
        for index, level_id in enumerate(TRADEDESK_EXIT_LEVEL_ORDER)
        if mask & (1 << index)
    ]


def normalize_compact_ladder(
    prices: list[Any], *, direction: str, entry_price: Any, target_price: Any,
    mintick: Any,
) -> list[dict[str, Any]]:
    if len(prices) != len(TRADEDESK_EXIT_LEVEL_ORDER):
        raise ValueError("ladder_prices must contain exactly 11 canonical prices")
    normalized = [Decimal(str(price)) for price in prices]
    tick = Decimal(str(mintick))
    entry = Decimal(str(entry_price))
    target = Decimal(str(target_price))
    if tick <= 0 or not tick.is_finite():
        raise ValueError("ladder_mintick must be positive and finite")
    if any(not price.is_finite() for price in normalized):
        raise ValueError("ladder prices must be finite")
    tolerance = tick / 2
    multiplier = Decimal(1 if direction == "LONG" else -1)
    groups: list[dict[str, Any]] = []
    for index, price in enumerate(normalized):
        existing = next(
            (group for group in groups if abs(group["level_price"] - price) <= tolerance),
            None,
        )
        if existing is None:
            groups.append({"level_ids": [], "level_price": price})
            existing = groups[-1]
        existing["level_ids"].append(TRADEDESK_EXIT_LEVEL_ORDER[index])
    eligible_groups = [
        group for group in groups
        if multiplier * (group["level_price"] - entry) > 0
        and multiplier * (target - group["level_price"]) >= 0
    ]
    eligible_groups.sort(key=lambda group: multiplier * (group["level_price"] - entry))
    orders = {id(group): index + 1 for index, group in enumerate(eligible_groups)}
    return [
        {
            **group,
            "eligible": id(group) in orders,
            "destination_order": orders.get(id(group)),
        }
        for group in groups
    ]


class FrozenExitLevelGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_ids: list[str] = Field(min_length=1)
    level_price: Decimal
    eligible: bool
    destination_order: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_group(self) -> "FrozenExitLevelGroup":
        if len(set(self.level_ids)) != len(self.level_ids):
            raise ValueError("frozen exit level IDs must be unique within a group")
        if not set(self.level_ids).issubset(TRADEDESK_EXIT_LEVEL_IDS):
            raise ValueError("unknown frozen exit level ID")
        if not self.level_price.is_finite():
            raise ValueError("frozen exit level price must be finite")
        if self.eligible != (self.destination_order is not None):
            raise ValueError("eligible frozen levels require destination_order")
        return self


class TerminalExitLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level_ids: list[str] = Field(min_length=1)
    level_price: Decimal

    @model_validator(mode="after")
    def validate_level(self) -> "TerminalExitLevel":
        if len(set(self.level_ids)) != len(self.level_ids):
            raise ValueError("terminal exit level IDs must be unique")
        if not set(self.level_ids).issubset(TRADEDESK_EXIT_LEVEL_IDS):
            raise ValueError("unknown terminal exit level ID")
        if not self.level_price.is_finite():
            raise ValueError("terminal exit level price must be finite")
        return self


class TradeDeskLifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0", "1.1", "1.2"]
    event_id: str = Field(min_length=1, max_length=224)
    setup_id: str = Field(min_length=1, max_length=160)
    event_type: Literal[
        "MSS_CONFIRMED",
        "RR_QUALIFIED",
        "GRADE_A",
        "GRADE_A_PLUS",
        "SETUP_FAILED",
        "SETUP_RETIRED",
        "TARGET_TAKEN",
        "ENTRY_TOUCHED",
        "ENTRY_CONFIRMED",
        "ENTRY_INVALIDATED",
        "ENTRY_STOPPED",
        "ENTRY_TARGET_TAKEN",
        "ENTRY_AMBIGUOUS",
        "ENTRY_EXIT_LEVEL_REACHED",
    ]
    symbol: str = Field(min_length=1, max_length=32)
    direction: Literal["LONG", "SHORT"]
    mss_at: int = Field(gt=0)
    event_at: int = Field(gt=0)
    sweep_price: Decimal
    target_price: Decimal
    target_side: Literal["BSL", "SSL"]
    grade: str | None = Field(max_length=32)
    rr_qualified_at: int | None = Field(default=None, gt=0)
    rr_source: Literal["SB", "BISI", "SIBI", "VI", "IFVG", "BREAKER", "OTE"] | None = None
    rr_reference_price: Decimal | None = None
    setup_rr: Decimal | None = None
    event_price: Decimal
    chart_timeframe: str = Field(min_length=1, max_length=32)
    range_timeframe: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=1024)
    entry_id: str | None = Field(default=None, min_length=1, max_length=192)
    entry_attempt: int | None = Field(default=None, gt=0)
    entry_source: Literal["SB", "BISI", "SIBI", "FVG", "VI", "IFVG", "BREAKER"] | None = None
    confirmation_method: Literal["CE_RECLAIM", "PROXIMAL_RECLAIM"] | None = None
    entry_zone_top: Decimal | None = None
    entry_zone_bottom: Decimal | None = None
    ote_top: Decimal | None = None
    ote_bottom: Decimal | None = None
    ote_confirmed_at: int | None = Field(default=None, gt=0)
    range_low: Decimal | None = None
    range_high: Decimal | None = None
    range_third: Literal["BOTTOM", "TOP"] | None = None
    ote_required: bool | None = None
    minimum_grade: Literal["Off", "A", "A+"] | None = None
    grade_at_touch: Literal["A", "A+"] | None = None
    grade_at_confirmation: Literal["A", "A+"] | None = None
    entry_touched_at: int | None = Field(default=None, gt=0)
    entry_confirmed_at: int | None = Field(default=None, gt=0)
    entry_price: Decimal | None = None
    stop_price: Decimal | None = None
    entry_rr: Decimal | None = None
    mrz_context_id: str | None = Field(default=None, max_length=512)
    exit_ladder_available: bool | None = None
    frozen_exit_ladder: list[FrozenExitLevelGroup] | None = None
    initial_risk: Decimal | None = None
    level_ids: list[str] | None = None
    level_mask: int | None = Field(
        default=None, ge=1, le=TRADEDESK_EXIT_LEVEL_MASK, exclude=True
    )
    level_price: Decimal | None = None
    excursion_r: Decimal | None = None
    contact_mode: Literal["RANGE_TOUCH", "GAP_CROSS"] | None = None
    mfe_pre_terminal_price: Decimal | None = None
    mfe_pre_terminal_r: Decimal | None = None
    mae_pre_terminal_price: Decimal | None = None
    mae_pre_terminal_r: Decimal | None = None
    mfe_inclusive_price: Decimal | None = None
    mfe_inclusive_r: Decimal | None = None
    mae_inclusive_price: Decimal | None = None
    mae_inclusive_r: Decimal | None = None
    best_level_pre_terminal_ids: list[str] | None = None
    best_level_pre_terminal_price: Decimal | None = None
    best_level_pre_terminal_r: Decimal | None = None
    best_level_pre_terminal_at: int | None = Field(default=None, gt=0)
    terminal_bar_levels_touched: list[TerminalExitLevel] | None = None
    terminal_level_mask: int | None = Field(
        default=None, ge=0, le=TRADEDESK_EXIT_LEVEL_MASK, exclude=True
    )
    reached_mask: int | None = Field(
        default=None, ge=0, le=TRADEDESK_EXIT_LEVEL_MASK, exclude=True
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_compact_schema_12(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        compact_keys = {
            "ladder_prices", "ladder_available", "ladder_mintick",
            "level_mask", "terminal_level_mask", "reached_mask",
        }
        uses_compact = bool(compact_keys.intersection(data))
        if data.get("schema_version") != "1.2" and uses_compact:
            raise ValueError("compact evidence requires schema_version=1.2")
        if "ladder_prices" in data:
            if "frozen_exit_ladder" in data or "exit_ladder_available" in data:
                raise ValueError("compact and verbose frozen ladder evidence cannot be mixed")
            prices = data.pop("ladder_prices")
            available = data.pop("ladder_available", bool(prices))
            mintick = data.pop("ladder_mintick", None)
            data["exit_ladder_available"] = available
            if available:
                if mintick is None:
                    raise ValueError("available compact ladder requires ladder_mintick")
                data["frozen_exit_ladder"] = normalize_compact_ladder(
                    prices, direction=data.get("direction"),
                    entry_price=data.get("entry_price"), target_price=data.get("target_price"),
                    mintick=mintick,
                )
            else:
                if prices or data.get("mrz_context_id") is not None:
                    raise ValueError("unavailable compact ladder must not contain MRZ geometry")
                data["frozen_exit_ladder"] = []
        elif "ladder_available" in data or "ladder_mintick" in data:
            raise ValueError("compact ladder metadata requires ladder_prices")
        if "level_mask" in data:
            if "level_ids" in data:
                raise ValueError("compact and verbose reached-level evidence cannot be mixed")
            data["level_ids"] = decode_tradedesk_level_mask(int(data["level_mask"]))
        confirmed = data.get("entry_price") is not None and data.get("stop_price") is not None
        if uses_compact and confirmed and data.get("initial_risk") is None:
            data["initial_risk"] = abs(
                Decimal(str(data["entry_price"])) - Decimal(str(data["stop_price"]))
            )
        if data.get("event_type") == "ENTRY_EXIT_LEVEL_REACHED" and data.get("excursion_r") is None:
            direction = Decimal(1 if data.get("direction") == "LONG" else -1)
            data["excursion_r"] = max(
                Decimal(0), direction * (
                    Decimal(str(data["level_price"])) - Decimal(str(data["entry_price"]))
                ) / Decimal(str(data["initial_risk"])),
            )
        if data.get("terminal_level_mask") is not None or data.get("reached_mask") is not None:
            if "terminal_bar_levels_touched" in data:
                raise ValueError("compact and verbose terminal-level evidence cannot be mixed")
            direction = Decimal(1 if data.get("direction") == "LONG" else -1)
            entry = Decimal(str(data["entry_price"]))
            risk = Decimal(str(data["initial_risk"]))
            pairs = (
                ("mfe_pre_terminal_price", "mfe_pre_terminal_r", True, True),
                ("mae_pre_terminal_price", "mae_pre_terminal_r", False, False),
                ("mfe_inclusive_price", "mfe_inclusive_r", True, False),
                ("mae_inclusive_price", "mae_inclusive_r", False, False),
            )
            for price_field, r_field, favorable, required in pairs:
                if required and data.get(price_field) is None:
                    raise ValueError(f"compact terminal event requires {price_field}")
                if data.get(price_field) is None:
                    continue
                move = direction * (Decimal(str(data[price_field])) - entry)
                data[r_field] = max(Decimal(0), move if favorable else -move) / risk
        return data

    @field_validator("event_id", "setup_id", "entry_id")
    @classmethod
    def validate_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if any(ord(character) < 32 for character in value):
            raise ValueError("identifier must be non-empty printable text")
        return value

    @field_validator("sweep_price", "target_price", "event_price")
    @classmethod
    def validate_finite_price(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("prices must be finite")
        return value

    @field_validator(
        "rr_reference_price",
        "setup_rr",
        "entry_zone_top",
        "entry_zone_bottom",
        "ote_top",
        "ote_bottom",
        "range_low",
        "range_high",
        "entry_price",
        "stop_price",
        "entry_rr",
        "initial_risk",
        "level_price",
        "excursion_r",
        "mfe_pre_terminal_price",
        "mfe_pre_terminal_r",
        "mae_pre_terminal_price",
        "mae_pre_terminal_r",
        "mfe_inclusive_price",
        "mfe_inclusive_r",
        "mae_inclusive_price",
        "mae_inclusive_r",
        "best_level_pre_terminal_price",
        "best_level_pre_terminal_r",
    )
    @classmethod
    def validate_finite_rr(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("numeric values must be finite")
        return value

    @model_validator(mode="after")
    def validate_entry_contract(self) -> "TradeDeskLifecyclePayload":
        entry_fields = (
            "entry_id",
            "entry_attempt",
            "entry_source",
            "confirmation_method",
            "entry_zone_top",
            "entry_zone_bottom",
            "ote_top",
            "ote_bottom",
            "ote_confirmed_at",
            "range_low",
            "range_high",
            "range_third",
            "ote_required",
            "minimum_grade",
            "grade_at_touch",
            "grade_at_confirmation",
            "entry_touched_at",
            "entry_confirmed_at",
            "entry_price",
            "stop_price",
            "entry_rr",
        )
        is_entry_event = self.event_type in TRADEDESK_ENTRY_EVENT_TYPES
        if not is_entry_event:
            if self.schema_version == "1.0" and any(
                getattr(self, field) is not None for field in entry_fields
            ):
                raise ValueError("schema 1.0 events cannot contain entry fields")
            return self

        if self.schema_version not in {"1.1", "1.2"}:
            raise ValueError("entry events require schema_version=1.1 or 1.2")

        required = (
            "entry_id",
            "entry_attempt",
            "entry_source",
            "confirmation_method",
            "entry_zone_top",
            "entry_zone_bottom",
            "range_low",
            "range_high",
            "range_third",
            "entry_touched_at",
        )
        missing = [field for field in required if getattr(self, field) is None]
        if missing:
            raise ValueError(f"entry event is missing required fields: {', '.join(missing)}")

        if self.ote_required is not False and (
            self.ote_top is None
            or self.ote_bottom is None
            or self.ote_confirmed_at is None
        ):
            raise ValueError(
                "OTE-required entry events require OTE bounds and confirmation time"
            )

        if self.entry_id != f"{self.setup_id}-E{self.entry_attempt}":
            raise ValueError("entry_id must be {setup_id}-E{entry_attempt}")
        if self.entry_zone_top <= self.entry_zone_bottom:
            raise ValueError("entry_zone_top must be greater than entry_zone_bottom")
        if self.ote_top is not None and self.ote_bottom is not None and self.ote_top <= self.ote_bottom:
            raise ValueError("ote_top must be greater than ote_bottom")
        if self.range_high <= self.range_low:
            raise ValueError("range_high must be greater than range_low")
        if (
            self.ote_confirmed_at is not None
            and self.entry_touched_at < self.ote_confirmed_at
        ):
            raise ValueError("entry touch cannot predate OTE confirmation")
        if self.entry_touched_at > self.event_at:
            raise ValueError("entry touch cannot be later than its event")
        if self.entry_touched_at <= self.mss_at:
            raise ValueError("entry touch must occur after MSS confirmation")
        if self.event_type == "ENTRY_TOUCHED" and self.event_at != self.entry_touched_at:
            raise ValueError("ENTRY_TOUCHED event time must equal entry_touched_at")

        expected_third = "BOTTOM" if self.direction == "LONG" else "TOP"
        if self.range_third != expected_third:
            raise ValueError(f"{self.direction} entries require range_third={expected_third}")
        if self.direction == "LONG" and self.entry_source == "SIBI":
            raise ValueError("LONG entry cannot use bearish SIBI as its source")
        if self.direction == "SHORT" and self.entry_source == "BISI":
            raise ValueError("SHORT entry cannot use bullish BISI as its source")

        tolerance = max(
            decimal_tick(self.entry_zone_top),
            decimal_tick(self.entry_zone_bottom),
            decimal_tick(self.range_low),
            decimal_tick(self.range_high),
        )
        third_ceiling = self.range_low + (self.range_high - self.range_low) / 3
        third_floor = self.range_high - (self.range_high - self.range_low) / 3
        if self.direction == "LONG" and (
            self.entry_zone_bottom < self.range_low - tolerance
            or self.entry_zone_top > third_ceiling + tolerance
        ):
            raise ValueError("LONG entry zone must be inside the bottom third")
        if self.direction == "SHORT" and (
            self.entry_zone_bottom < third_floor - tolerance
            or self.entry_zone_top > self.range_high + tolerance
        ):
            raise ValueError("SHORT entry zone must be inside the top third")
        if self.ote_required is not False and (
            self.entry_zone_bottom < self.ote_bottom - tolerance
            or self.entry_zone_top > self.ote_top + tolerance
        ):
            raise ValueError("entry zone must be inside the confirmed OTE band")

        confirmed_event = self.event_type in {
            "ENTRY_CONFIRMED",
            "ENTRY_EXIT_LEVEL_REACHED",
            "ENTRY_STOPPED",
            "ENTRY_TARGET_TAKEN",
            "ENTRY_AMBIGUOUS",
        }
        confirmed_fields = (
            "entry_confirmed_at",
            "entry_price",
            "stop_price",
            "entry_rr",
        )
        if confirmed_event:
            missing = [field for field in confirmed_fields if getattr(self, field) is None]
            if missing:
                raise ValueError(
                    f"confirmed entry event is missing required fields: {', '.join(missing)}"
                )
            if self.entry_confirmed_at <= self.entry_touched_at:
                raise ValueError("entry confirmation must occur after entry touch")
            if self.entry_confirmed_at > self.event_at:
                raise ValueError("entry confirmation cannot be later than its event")
            if self.event_type == "ENTRY_CONFIRMED" and self.event_at != self.entry_confirmed_at:
                raise ValueError("ENTRY_CONFIRMED event time must equal entry_confirmed_at")
            if self.event_type in {
                "ENTRY_STOPPED",
                "ENTRY_TARGET_TAKEN",
                "ENTRY_AMBIGUOUS",
            } and self.event_at <= self.entry_confirmed_at:
                raise ValueError("terminal entry event must occur after entry confirmation")
            if self.entry_rr < 0:
                raise ValueError("entry_rr must be non-negative")
            confirmation_tolerance = max(
                decimal_tick(self.entry_price),
                decimal_tick(self.range_low),
                decimal_tick(self.range_high),
            )
            if self.direction == "LONG":
                if not (self.stop_price < self.entry_price < self.target_price):
                    raise ValueError("LONG entry requires stop < entry < target")
                third_ceiling = self.range_low + (self.range_high - self.range_low) / 3
                if self.entry_price > third_ceiling + confirmation_tolerance:
                    raise ValueError("LONG entry price must be in the bottom third")
            else:
                if not (self.target_price < self.entry_price < self.stop_price):
                    raise ValueError("SHORT entry requires target < entry < stop")
                if self.entry_price < third_floor - confirmation_tolerance:
                    raise ValueError("SHORT entry price must be in the top third")
        elif any(getattr(self, field) is not None for field in confirmed_fields):
            raise ValueError("unconfirmed entry events cannot contain confirmation fields")

        evidence_fields = (
            "mrz_context_id", "exit_ladder_available", "frozen_exit_ladder",
            "initial_risk", "level_ids", "level_mask", "level_price", "excursion_r", "contact_mode",
            "mfe_pre_terminal_price", "mfe_pre_terminal_r", "mae_pre_terminal_price",
            "mae_pre_terminal_r", "mfe_inclusive_price", "mfe_inclusive_r",
            "mae_inclusive_price", "mae_inclusive_r", "best_level_pre_terminal_ids",
            "best_level_pre_terminal_price", "best_level_pre_terminal_r",
            "best_level_pre_terminal_at", "terminal_bar_levels_touched",
            "terminal_level_mask", "reached_mask",
        )
        if self.schema_version != "1.2" and any(
            getattr(self, field) is not None for field in evidence_fields
        ):
            raise ValueError("schema 1.2 evidence requires schema_version=1.2")

        if self.schema_version == "1.2" and self.event_type == "ENTRY_CONFIRMED":
            if self.initial_risk is None or self.initial_risk <= 0:
                raise ValueError("schema 1.2 confirmation requires positive initial_risk")
            if self.exit_ladder_available is None or self.frozen_exit_ladder is None:
                raise ValueError("schema 1.2 confirmation requires frozen ladder evidence")
            if self.exit_ladder_available:
                if not self.mrz_context_id or not self.frozen_exit_ladder:
                    raise ValueError("available frozen ladder requires MRZ context and levels")
                all_ids = [level_id for group in self.frozen_exit_ladder for level_id in group.level_ids]
                if len(all_ids) != 11 or set(all_ids) != TRADEDESK_EXIT_LEVEL_IDS:
                    raise ValueError("frozen ladder must contain all 11 canonical identities")
                orders = sorted(
                    group.destination_order
                    for group in self.frozen_exit_ladder
                    if group.destination_order is not None
                )
                if orders != list(range(1, len(orders) + 1)):
                    raise ValueError("eligible frozen ladder order must be contiguous")
            elif self.mrz_context_id is not None or self.frozen_exit_ladder:
                raise ValueError("unavailable frozen ladder must not contain MRZ geometry")

        if self.event_type == "ENTRY_EXIT_LEVEL_REACHED":
            if self.schema_version != "1.2":
                raise ValueError("exit-level reaches require schema_version=1.2")
            if not self.level_ids or self.level_price is None or self.excursion_r is None:
                raise ValueError("exit-level reach is missing level evidence")
            if self.level_mask is None and self.contact_mode is None:
                raise ValueError("verbose exit-level reach requires contact_mode")
            if not set(self.level_ids).issubset(TRADEDESK_EXIT_LEVEL_IDS):
                raise ValueError("exit-level reach contains unknown level ID")
            if len(self.level_ids) != len(set(self.level_ids)):
                raise ValueError("exit-level reach IDs must be unique")
            if self.excursion_r < 0:
                raise ValueError("excursion_r must be non-negative")

        terminal_event = self.event_type in {
            "ENTRY_STOPPED", "ENTRY_TARGET_TAKEN", "ENTRY_AMBIGUOUS"
        }
        if self.schema_version == "1.2" and terminal_event:
            terminal_required = (
                ("initial_risk", "mfe_pre_terminal_price", "mfe_pre_terminal_r")
                if self.terminal_level_mask is not None or self.reached_mask is not None
                else (
                    "initial_risk", "mfe_pre_terminal_price", "mfe_pre_terminal_r",
                    "mae_pre_terminal_price", "mae_pre_terminal_r", "mfe_inclusive_price",
                    "mfe_inclusive_r", "mae_inclusive_price", "mae_inclusive_r",
                )
            )
            missing = [field for field in terminal_required if getattr(self, field) is None]
            if missing:
                raise ValueError(f"schema 1.2 terminal event is missing: {', '.join(missing)}")
            if (
                self.terminal_bar_levels_touched is None
                and self.terminal_level_mask is None
                and self.reached_mask is None
            ):
                raise ValueError("schema 1.2 terminal event requires terminal level evidence")
            if self.initial_risk <= 0:
                raise ValueError("initial_risk must be positive")
            for field in (
                "mfe_pre_terminal_r", "mae_pre_terminal_r",
                "mfe_inclusive_r", "mae_inclusive_r",
            ):
                if getattr(self, field) is not None and getattr(self, field) < 0:
                    raise ValueError(f"{field} must be non-negative")
            best = (
                self.best_level_pre_terminal_ids,
                self.best_level_pre_terminal_price,
                self.best_level_pre_terminal_r,
                self.best_level_pre_terminal_at,
            )
            if any(value is not None for value in best) and not all(value is not None for value in best):
                raise ValueError("best pre-terminal level fields must be all present or all absent")
            if self.best_level_pre_terminal_ids is not None:
                if not set(self.best_level_pre_terminal_ids).issubset(TRADEDESK_EXIT_LEVEL_IDS):
                    raise ValueError("best pre-terminal level contains unknown ID")
                if len(self.best_level_pre_terminal_ids) != len(set(self.best_level_pre_terminal_ids)):
                    raise ValueError("best pre-terminal level IDs must be unique")
                if self.best_level_pre_terminal_r < 0:
                    raise ValueError("best_level_pre_terminal_r must be non-negative")
                if not (
                    self.entry_confirmed_at
                    < self.best_level_pre_terminal_at
                    < self.event_at
                ):
                    raise ValueError("best pre-terminal time must be strictly before terminal")

        grade_rank = {None: 0, "A": 1, "A+": 2}
        required_rank = {None: 0, "Off": 0, "A": 1, "A+": 2}[self.minimum_grade]
        if grade_rank[self.grade_at_touch] < required_rank:
            raise ValueError("grade_at_touch does not meet minimum_grade")
        if confirmed_event and grade_rank[self.grade_at_confirmation] < required_rank:
            raise ValueError("grade_at_confirmation does not meet minimum_grade")

        return self
