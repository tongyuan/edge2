#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.domain import Observation, ObservationType, Route
from app.state_engine import replay_symbol


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def event(index: int, price: str, route: Route = Route.BTD) -> Observation:
    return Observation(
        id=index,
        event_id=f"acceptance-{route.value.lower()}-{index}",
        schema_version="4.3",
        symbol="SPXUSDT",
        route=route,
        observation_type=ObservationType.RECLAIM if route is Route.BTD else ObservationType.REJECTION,
        observation_price=Decimal(price),
        observation_price_tick=Decimal("0.01"),
        ipda_20w_high=Decimal("200"),
        ipda_20w_low=Decimal("100"),
        observed_at=BASE_TIME + timedelta(seconds=index),
        received_at=BASE_TIME + timedelta(seconds=index),
    )


def summary(result) -> dict[str, object]:
    active = result.active_mrz
    return {
        "route_owner": active.route_owner.value,
        "core_mrz_lower": str(active.core_mrz_lower),
        "core_mrz_upper": str(active.core_mrz_upper),
        "core_mrz_midpoint": str(active.core_mrz_midpoint),
        "structural_location": active.structural_location.value,
        "confirming_observation_count": active.confirming_observation_count,
        "transition_types": [item.event_type.value for item in result.transitions],
    }


def main() -> int:
    btd_prices = ("110", "140", "110.3", "132", "110.7", "111", "120", "120.2", "120.4", "120.6")
    btd = replay_symbol(event(index, price) for index, price in enumerate(btd_prices, 1))
    str_prices = ("180", "180.2", "180.4", "180.6", "170.6", "170.4", "170.2", "170")
    str_result = replay_symbol(
        event(index, price, Route.STR) for index, price in enumerate(str_prices, 1)
    )
    print(json.dumps({"BTD_activation_and_migration": summary(btd), "STR_mirror": summary(str_result)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
