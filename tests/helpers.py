from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain import Observation, ObservationType, Route


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def observation(
    index: int,
    price: str | Decimal,
    *,
    route: Route = Route.BTD,
    symbol: str = "SPXUSDT",
    ipda_low: str | Decimal = "100",
    ipda_high: str | Decimal = "200",
    tick: str | Decimal = "0.01",
    event_id: str | None = None,
    observed_offset: int | None = None,
    received_offset: int | None = None,
) -> Observation:
    return Observation(
        id=index,
        event_id=event_id or f"event-{index}",
        schema_version="4.3",
        symbol=symbol,
        route=route,
        observation_type=(ObservationType.RECLAIM if route is Route.BTD else ObservationType.REJECTION),
        observation_price=Decimal(price),
        observation_price_tick=Decimal(tick),
        ipda_20w_high=Decimal(ipda_high),
        ipda_20w_low=Decimal(ipda_low),
        observed_at=BASE_TIME + timedelta(seconds=observed_offset if observed_offset is not None else index),
        received_at=BASE_TIME + timedelta(seconds=received_offset if received_offset is not None else index),
    )
