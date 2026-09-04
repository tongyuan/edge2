from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Route(StrEnum):
    BTD = "BTD"
    STR = "STR"


class ObservationType(StrEnum):
    RECLAIM = "reclaim"
    REJECTION = "rejection"


class StructuralLocation(StrEnum):
    DEEP_DISCOUNT = "deep_discount_core_mrz"
    SHALLOW_DISCOUNT = "shallow_discount_core_mrz"
    SHALLOW_PREMIUM = "shallow_premium_core_mrz"
    DEEP_PREMIUM = "deep_premium_core_mrz"


class PriceLocation(StrEnum):
    DEEP_DISCOUNT = "deep_discount"
    SHALLOW_DISCOUNT = "shallow_discount"
    SHALLOW_PREMIUM = "shallow_premium"
    DEEP_PREMIUM = "deep_premium"
    BELOW_IPDA_RANGE = "below_ipda_range"
    ABOVE_IPDA_RANGE = "above_ipda_range"


class MRZEventType(StrEnum):
    ACTIVATED = "MRZ_ACTIVATED"
    MIGRATED = "MRZ_MIGRATED"
    ROUTE_CHANGED = "ROUTE_CHANGED"


class ActivationSource(StrEnum):
    PRODUCTION_QUALIFIED = "PRODUCTION_QUALIFIED"
    OPERATOR_PROMOTED = "OPERATOR_PROMOTED"


@dataclass(frozen=True, slots=True)
class Observation:
    id: int
    event_id: str
    schema_version: str
    symbol: str
    route: Route
    observation_type: ObservationType
    observation_price: Decimal
    observation_price_tick: Decimal
    ipda_20w_high: Decimal
    ipda_20w_low: Decimal
    observed_at: datetime
    received_at: datetime

    @property
    def ipda_width(self) -> Decimal:
        return self.ipda_20w_high - self.ipda_20w_low

    @property
    def order_key(self) -> tuple[datetime, datetime, int]:
        return self.observed_at, self.received_at, self.id


@dataclass(frozen=True, slots=True)
class Cluster:
    members: tuple[Observation, ...]
    lower: Decimal
    upper: Decimal
    midpoint: Decimal
    normalized_span: Decimal

    @property
    def observation_count(self) -> int:
        return len(self.members)

    @property
    def formation_started_at(self) -> datetime:
        return min(member.observed_at for member in self.members)

    @property
    def formation_completed_at(self) -> datetime:
        return max(member.observed_at for member in self.members)

    @property
    def formation_duration_seconds(self) -> Decimal:
        duration = self.formation_completed_at - self.formation_started_at
        whole_seconds = (duration.days * 86400) + duration.seconds
        return Decimal(whole_seconds) + (Decimal(duration.microseconds) / Decimal("1000000"))


@dataclass(frozen=True, slots=True)
class ActiveMRZ:
    symbol: str
    route_owner: Route
    core_mrz_lower: Decimal
    core_mrz_upper: Decimal
    core_mrz_midpoint: Decimal
    structural_location: StructuralLocation
    confirming_observation_count: int
    supporting_observation_count: int
    activated_at: datetime
    activation_event_id: str
    formation_started_at: datetime | None
    formation_completed_at: datetime | None
    formation_duration_seconds: Decimal | None
    ipda_20w_high_at_activation: Decimal
    ipda_20w_low_at_activation: Decimal
    ipda_width_at_activation: Decimal
    normalized_span_at_activation: Decimal
    instrument_tick: Decimal
    activation_source: ActivationSource = ActivationSource.PRODUCTION_QUALIFIED

    @property
    def width(self) -> Decimal:
        return self.core_mrz_upper - self.core_mrz_lower

    @property
    def effective_width(self) -> Decimal:
        return max(self.width, self.instrument_tick)

    @property
    def lower_migration_boundary(self) -> Decimal:
        return self.core_mrz_lower - (Decimal("2") * self.effective_width)

    @property
    def upper_migration_boundary(self) -> Decimal:
        return self.core_mrz_upper + (Decimal("2") * self.effective_width)


@dataclass(frozen=True, slots=True)
class MRZTransition:
    sequence: int
    event_type: MRZEventType
    symbol: str
    route_owner: Route
    previous_route_owner: Route | None
    occurred_at: datetime
    trigger_event_id: str
    old_mrz: ActiveMRZ | None
    new_mrz: ActiveMRZ
    details: dict[str, Any]

    @property
    def event_key(self) -> str:
        return f"{self.symbol}:{self.sequence}:{self.event_type}:{self.trigger_event_id}"


@dataclass(frozen=True, slots=True)
class ReplayResult:
    symbol: str
    active_mrz: ActiveMRZ | None
    transitions: tuple[MRZTransition, ...]
    latest_observation: Observation | None
