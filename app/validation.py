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


POLR_ENTRY_EVENT_TYPES = {
    "ENTRY_TOUCHED",
    "ENTRY_CONFIRMED",
    "ENTRY_INVALIDATED",
    "ENTRY_STOPPED",
    "ENTRY_AMBIGUOUS",
}


class POLRLifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0", "1.1"]
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
        "ENTRY_AMBIGUOUS",
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
    rr_source: Literal["SB", "BISI", "SIBI", "VI", "IFVG", "OTE"] | None = None
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
    )
    @classmethod
    def validate_finite_rr(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("numeric values must be finite")
        return value

    @model_validator(mode="after")
    def validate_entry_contract(self) -> "POLRLifecyclePayload":
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
        is_entry_event = self.event_type in POLR_ENTRY_EVENT_TYPES
        if not is_entry_event:
            if self.schema_version == "1.0" and any(
                getattr(self, field) is not None for field in entry_fields
            ):
                raise ValueError("schema 1.0 events cannot contain entry fields")
            return self

        if self.schema_version != "1.1":
            raise ValueError("entry events require schema_version=1.1")

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
            "ENTRY_STOPPED",
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
            if self.entry_confirmed_at < self.entry_touched_at:
                raise ValueError("entry confirmation cannot predate entry touch")
            if self.entry_confirmed_at > self.event_at:
                raise ValueError("entry confirmation cannot be later than its event")
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

        grade_rank = {None: 0, "A": 1, "A+": 2}
        required_rank = {None: 0, "Off": 0, "A": 1, "A+": 2}[self.minimum_grade]
        if grade_rank[self.grade_at_touch] < required_rank:
            raise ValueError("grade_at_touch does not meet minimum_grade")
        if confirmed_event and grade_rank[self.grade_at_confirmation] < required_rank:
            raise ValueError("grade_at_confirmation does not meet minimum_grade")

        return self
