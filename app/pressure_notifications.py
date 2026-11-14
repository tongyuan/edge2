from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from app.domain import Observation
from app.mrz_robustness import MRZRobustnessService, RobustnessInputProvider


LOGGER = logging.getLogger("edge2.notifications")
PressureStateWriter = Callable[[Mapping[str, Any], str], int | None]


class PressureNotificationCoordinator:
    """Pressure-only report generation, separate from shared delivery infrastructure."""

    def __init__(
        self,
        input_provider: RobustnessInputProvider | None,
        state_writer: PressureStateWriter,
    ) -> None:
        self.input_provider = input_provider
        self.state_writer = state_writer

    def reconcile(self, trigger_event_id: str | None = None) -> None:
        if self.input_provider is None:
            return
        try:
            active_mrzs, observations, migration_provenance = self.input_provider()
            if not active_mrzs:
                return
            observations_by_symbol: dict[str, list[Observation]] = {}
            trigger_symbol = None
            for observation in observations:
                observations_by_symbol.setdefault(observation.symbol, []).append(
                    observation
                )
                if observation.event_id == trigger_event_id:
                    trigger_symbol = observation.symbol
            if trigger_event_id is not None and trigger_symbol is None:
                return

            generated_at = datetime.now(timezone.utc)
            robustness_service = MRZRobustnessService(
                lambda: (active_mrzs, observations, migration_provenance)
            )
            for active in active_mrzs:
                if trigger_symbol is not None and active.symbol != trigger_symbol:
                    continue
                symbol_observations = observations_by_symbol.get(active.symbol, [])
                if not symbol_observations:
                    continue
                evaluation_trigger = max(
                    symbol_observations,
                    key=lambda item: (item.received_at, item.id),
                )
                report = robustness_service.active_mrz_report(
                    active,
                    symbol_observations,
                    generated_at,
                    migration_provenance.get(active.symbol, {"has_migrated": False}),
                )
                self.state_writer(report, evaluation_trigger.event_id)
        except Exception:
            LOGGER.exception(
                "Post-activation pressure reconciliation failed; MRZ authority "
                "and other notifications are unaffected",
                extra={"trigger_event_id": trigger_event_id},
            )
