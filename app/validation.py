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


class POLRLifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal["1.0"]
    event_id: str = Field(min_length=1, max_length=160)
    setup_id: str = Field(min_length=1, max_length=160)
    event_type: Literal[
        "MSS_CONFIRMED",
        "RR_QUALIFIED",
        "GRADE_A",
        "GRADE_A_PLUS",
        "SETUP_FAILED",
        "SETUP_RETIRED",
        "TARGET_TAKEN",
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

    @field_validator("event_id", "setup_id")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("identifier must be non-empty printable text")
        return value

    @field_validator("sweep_price", "target_price", "event_price")
    @classmethod
    def validate_finite_price(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("prices must be finite")
        return value

    @field_validator("rr_reference_price", "setup_rr")
    @classmethod
    def validate_finite_rr(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("numeric values must be finite")
        return value
