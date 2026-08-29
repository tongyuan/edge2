from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Iterable, Mapping, Sequence

from app.activation_feasibility import LOW_SAMPLE_SEQUENCE_THRESHOLD
from app.concentration import MIN_CLUSTER_OBSERVATIONS
from app.domain import MRZEventType, Observation, Route
from app.episode_replay import (
    Episode,
    first_timing,
    reconstruct_episodes,
    route_interpretation,
    signed_displacement,
)
from app.mrz_robustness import MRZRobustnessService, decimal_text, duration_seconds, iso, median_decimal


ALGORITHM = "A"
POLICY_ALLOWANCES = (
    Decimal("0.0100"),
    Decimal("0.0150"),
    Decimal("0.0200"),
)
EARLY_MIGRATION_MAX_POST_ACTIVATION_OBSERVATIONS = MIN_CLUSTER_OBSERVATIONS
EARLY_BEHAVIOR_MAX_POST_ACTIVATION_OBSERVATIONS = MIN_CLUSTER_OBSERVATIONS

ObservationReader = Callable[[], Sequence[Observation]]
HistoryKey = tuple[str, Route]


def allowance_percent(allowance: Decimal) -> str:
    return format(
        (allowance * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        ),
        "f",
    )


def rate_payload(numerator: int, denominator: int) -> dict[str, object]:
    percentage = (
        Decimal(numerator) * Decimal("100") / Decimal(denominator)
        if denominator
        else None
    )
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percentage": (
            decimal_text(percentage.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
            if percentage is not None
            else None
        ),
    }


def median_text(values: Iterable[Decimal]) -> str | None:
    return decimal_text(median_decimal(tuple(values)))


def _history_id(key: HistoryKey) -> str:
    return f"{key[0]}:{key[1].value}"


class MRZRobustnessReportService:
    """Read-only policy replay and post-activation durability aggregation."""

    def __init__(
        self,
        observation_reader: ObservationReader,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._observation_reader = observation_reader
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._measurement_service = MRZRobustnessService(lambda: ((), (), {}))

    def generate_report(self) -> dict[str, object]:
        observations = tuple(self._observation_reader())
        generated_at = self._clock()
        data_as_of = max((item.observed_at for item in observations), default=None)
        grouped: dict[HistoryKey, list[Observation]] = defaultdict(list)
        for observation in observations:
            grouped[(observation.symbol, observation.route)].append(observation)
        histories = {
            key: tuple(sorted(rows, key=lambda item: item.order_key))
            for key, rows in sorted(
                grouped.items(),
                key=lambda item: (item[0][0], item[0][1].value),
            )
            if len(rows) >= MIN_CLUSTER_OBSERVATIONS
        }

        records_by_allowance = {
            allowance: self._policy_records(histories, allowance)
            for allowance in POLICY_ALLOWANCES
        }
        policy_summaries = [
            self._policy_summary(
                allowance,
                records_by_allowance[allowance],
                len(histories),
            )
            for allowance in POLICY_ALLOWANCES
        ]
        production_records = records_by_allowance[POLICY_ALLOWANCES[0]]
        production_summary = policy_summaries[0]
        incremental_cohorts = self._incremental_cohorts(records_by_allowance)
        symbol_details = self._symbol_details(records_by_allowance)
        production_with_evidence = sum(
            int(record["post_activation_observation_count"]) > 0
            for record in production_records.values()
        )
        production_resolved = sum(
            int(record["structural_response"]["resolved_outcome_count"]) > 0
            for record in production_records.values()
        )
        completed = int(production_summary["completed_lifecycle_count"])

        return {
            "title": "MRZ Robustness",
            "mode": (
                "Read-only post-activation research. No production activation, migration, "
                "ownership, or configuration state is changed."
            ),
            "generated_at": iso(generated_at),
            "data_as_of": iso(data_as_of),
            "sample_confidence": {
                "status": (
                    "PRELIMINARY"
                    if len(histories) < LOW_SAMPLE_SEQUENCE_THRESHOLD
                    else "OBSERVED_SAMPLE"
                ),
                "label": (
                    "Sample confidence · Preliminary"
                    if len(histories) < LOW_SAMPLE_SEQUENCE_THRESHOLD
                    else "Sample confidence · Observed sample"
                ),
                "eligible_symbol_route_histories": len(histories),
                "minimum_history_threshold": LOW_SAMPLE_SEQUENCE_THRESHOLD,
                "production_mrz_formations": len(production_records),
                "production_formations_with_post_activation_evidence": production_with_evidence,
                "production_resolved_case_count": production_resolved,
                "production_unresolved_case_count": len(production_records) - production_resolved,
                "completed_migration_lifecycles": completed,
                "production_formed_denominator": len(histories),
            },
            "current_production_robustness": {
                "algorithm": ALGORITHM,
                "minimum_observations": MIN_CLUSTER_OBSERVATIONS,
                "allowance_percent": allowance_percent(POLICY_ALLOWANCES[0]),
                "label": "Algorithm A · 4 observations · 1.00% allowance",
                **production_summary,
            },
            "cross_symbol_robustness": list(production_records.values()),
            "migration_pressure_summary": self._migration_pressure_summary(
                production_records
            ),
            "policy_robustness_comparison": policy_summaries,
            "incremental_cohorts": incremental_cohorts,
            "symbol_level_detail": symbol_details,
            "evidence_interpretation": self._evidence_interpretation(
                len(histories),
                policy_summaries,
                incremental_cohorts,
            ),
            "methodology": {
                "sampling_unit": "eligible symbol-route history",
                "formation": (
                    "Each policy independently replays Algorithm A with exactly four "
                    "observations and its own allowance, activation time, and frozen bounds."
                ),
                "post_activation": (
                    "Only canonical observations strictly after that policy's activation "
                    "trigger are measured through migration or available history."
                ),
                "structural_response": (
                    "Each post-activation observation reuses the shared canonical "
                    "signed-displacement classifier: above the frozen midpoint "
                    "supports BTD and is adverse to STR; below supports STR and is adverse "
                    "to BTD; an exact midpoint observation is neutral/unresolved."
                ),
                "resolved_outcome": (
                    "A resolved outcome is a post-activation observation classified as "
                    "route-supportive or route-adverse. Neutral observations are excluded "
                    "from both rate denominators."
                ),
                "overall_aggregation": (
                    "BTD and STR are shown separately. Their overall counts may also be "
                    "combined because both use the same route-relative supportive/adverse "
                    "categories and the same resolved-outcome denominator."
                ),
                "early_adverse": (
                    "Research-only: a formed MRZ has an adverse outcome within its first "
                    f"{EARLY_BEHAVIOR_MAX_POST_ACTIVATION_OBSERVATIONS} post-activation observations."
                ),
                "containment": (
                    "post-activation observations inside the inclusive frozen MRZ divided "
                    "by total post-activation observations"
                ),
                "observed_lifespan": (
                    "activation to deterministic migration; ongoing lifecycles are censored "
                    "at the latest available observation and reported separately"
                ),
                "migration_pressure": (
                    "post-activation observations outside the existing frozen migration "
                    "envelope; successor concentration is reported separately"
                ),
                "early_migration": (
                    "migration confirmed by the fourth post-activation observation, the "
                    "earliest possible confirmation under the fixed four-observation rule"
                ),
                "geometry_note": (
                    "Wider formation allowances may produce wider frozen MRZs and wider "
                    "migration envelopes. Containment, lifespan, and migration-pressure "
                    "metrics are therefore secondary lifecycle diagnostics."
                ),
            },
            "invariants": {
                "schema_version": "4.3 unchanged",
                "minimum_observations": MIN_CLUSTER_OBSERVATIONS,
                "production_allowance": "1.00% unchanged",
                "persistence": "No replayed MRZ is persisted",
                "production_recommendation": "None",
            },
        }

    def _policy_records(
        self,
        histories: Mapping[HistoryKey, Sequence[Observation]],
        allowance: Decimal,
    ) -> dict[HistoryKey, dict[str, object]]:
        records: dict[HistoryKey, dict[str, object]] = {}
        for key, rows in histories.items():
            reconstruction = reconstruct_episodes(
                rows,
                minimum_required_count=MIN_CLUSTER_OBSERVATIONS,
                concentration_threshold=allowance,
            )
            if not reconstruction.episodes:
                continue
            episode = reconstruction.episodes[0]
            records[key] = self._episode_record(key, episode, allowance)
        return records

    def _episode_record(
        self,
        key: HistoryKey,
        episode: Episode,
        allowance: Decimal,
    ) -> dict[str, object]:
        completed = episode.termination_event_type is MRZEventType.MIGRATED
        stop = (
            episode.termination_index + 1
            if episode.termination_index is not None
            else len(episode.source_observations)
        )
        evidence_rows = episode.source_observations[:stop]
        observed_end = (
            episode.ended_at
            if completed and episode.ended_at is not None
            else evidence_rows[-1].observed_at
        )
        migration = {
            "has_migrated": completed,
            "migrated_at": iso(episode.ended_at) if completed else None,
            "direction": episode.migration_direction if completed else None,
        }
        measurement = self._measurement_service.active_mrz_report(
            episode.active_mrz,
            evidence_rows,
            observed_end,
            migration,
        )
        first_pressure_at, first_pressure_seconds = self._first_pressure(
            episode,
            evidence_rows,
        )
        post_count = int(
            measurement["robustness_evidence"]["post_activation_observation_count"]
        )
        structural_response = self._structural_response(episode)
        time_to_migration = (
            duration_seconds(episode.active_mrz.activated_at, episode.ended_at)
            if completed and episode.ended_at is not None
            else None
        )
        pressure_status = str(measurement["migration_pressure"]["status"])
        if completed or pressure_status == "MIGRATION_CANDIDATE":
            lifecycle_status = "MIGRATION_CANDIDATE"
            lifecycle_label = "Migration Candidate"
        elif pressure_status == "UNDER_PRESSURE":
            lifecycle_status = "UNDER_PRESSURE"
            lifecycle_label = "Under Pressure"
        elif pressure_status == "STABLE":
            lifecycle_status = "STABLE"
            lifecycle_label = "Stable"
        else:
            lifecycle_status = "NOT_YET_ASSESSABLE"
            lifecycle_label = "Not yet assessable"

        return {
            "formed": True,
            "history_id": _history_id(key),
            "symbol": key[0],
            "route": key[1].value,
            "mechanical_lifecycle_status": lifecycle_status,
            "mechanical_lifecycle_label": lifecycle_label,
            "mrz": {
                "lower": decimal_text(episode.active_mrz.core_mrz_lower),
                "upper": decimal_text(episode.active_mrz.core_mrz_upper),
                "midpoint": decimal_text(episode.active_mrz.core_mrz_midpoint),
                "structural_location": episode.active_mrz.structural_location.value,
            },
            "activated_at": iso(episode.active_mrz.activated_at),
            "formation_policy": {
                "algorithm": ALGORITHM,
                "minimum_observations": MIN_CLUSTER_OBSERVATIONS,
                "allowance_percent": allowance_percent(allowance),
            },
            "post_activation_observation_count": post_count,
            "structural_response": structural_response,
            "containment": dict(measurement["containment"]),
            "observed_lifespan_seconds": decimal_text(
                duration_seconds(episode.active_mrz.activated_at, observed_end)
            ),
            "lifecycle": {
                "completed": completed,
                "censored": not completed,
                "ended_at": iso(episode.ended_at) if completed else None,
                "time_to_migration_seconds": decimal_text(time_to_migration),
                "early_migration": (
                    completed
                    and post_count
                    <= EARLY_MIGRATION_MAX_POST_ACTIVATION_OBSERVATIONS
                ),
            },
            "boundary_pressure": dict(measurement["boundary_pressure"]),
            "midpoint_stability": dict(measurement["mrz_displacement"]),
            "route_integrity": dict(measurement["route_integrity"]),
            "migration_pressure": {
                **dict(measurement["migration_pressure"]),
                "first_pressure_at": iso(first_pressure_at),
                "time_to_first_pressure_seconds": decimal_text(
                    first_pressure_seconds
                ),
            },
            "successor_watch": dict(measurement["successor_watch"]),
        }

    @staticmethod
    def _structural_response(episode: Episode) -> dict[str, object]:
        active = episode.active_mrz
        classifications = tuple(
            route_interpretation(
                active.route_owner,
                signed_displacement(active, observation),
            )
            for observation in episode.post_activation_observations
        )
        supportive_count = classifications.count("ROUTE_SUPPORTIVE")
        adverse_count = classifications.count("ROUTE_ADVERSE")
        neutral_count = classifications.count("NEUTRAL")
        resolved_count = supportive_count + adverse_count
        first_supportive = first_timing(
            episode,
            lambda _index, observation: route_interpretation(
                active.route_owner,
                signed_displacement(active, observation),
            )
            == "ROUTE_SUPPORTIVE",
        )
        first_adverse = first_timing(
            episode,
            lambda _index, observation: route_interpretation(
                active.route_owner,
                signed_displacement(active, observation),
            )
            == "ROUTE_ADVERSE",
        )
        early_classifications = classifications[
            :EARLY_BEHAVIOR_MAX_POST_ACTIVATION_OBSERVATIONS
        ]

        def timing_payload(
            timing: tuple[int, Decimal] | None,
        ) -> dict[str, object]:
            observed_at = (
                episode.post_activation_observations[timing[0] - 1].observed_at
                if timing
                else None
            )
            return {
                "observation_number": timing[0] if timing else None,
                "seconds_from_activation": (
                    decimal_text(
                        duration_seconds(active.activated_at, observed_at)
                    )
                    if observed_at is not None
                    else None
                ),
            }

        return {
            "supportive_outcome_count": supportive_count,
            "adverse_outcome_count": adverse_count,
            "neutral_unresolved_outcome_count": neutral_count,
            "resolved_outcome_count": resolved_count,
            "supportive_rate": rate_payload(supportive_count, resolved_count),
            "adverse_rate": rate_payload(adverse_count, resolved_count),
            "supportive_to_adverse_balance": f"{supportive_count} : {adverse_count}",
            "first_supportive": timing_payload(first_supportive),
            "first_adverse": timing_payload(first_adverse),
            "early_adverse": "ROUTE_ADVERSE" in early_classifications,
            "early_window_observation_count": EARLY_BEHAVIOR_MAX_POST_ACTIVATION_OBSERVATIONS,
            "classifier": "ROUTE_ROLE_SIGNED_DISPLACEMENT",
        }

    def _first_pressure(
        self,
        episode: Episode,
        evidence_rows: Sequence[Observation],
    ) -> tuple[datetime | None, Decimal | None]:
        for index in range(episode.activation_index + 1, len(evidence_rows)):
            observation = evidence_rows[index]
            measurement = self._measurement_service.active_mrz_report(
                episode.active_mrz,
                evidence_rows[: index + 1],
                observation.observed_at,
                {"has_migrated": False},
            )
            if measurement["migration_pressure"]["status"] in {
                "UNDER_PRESSURE",
                "MIGRATION_CANDIDATE",
            }:
                return observation.observed_at, duration_seconds(
                    episode.active_mrz.activated_at,
                    observation.observed_at,
                )
        return None, None

    def _policy_summary(
        self,
        allowance: Decimal,
        records: Mapping[HistoryKey, Mapping[str, object]],
        eligible_history_count: int,
    ) -> dict[str, object]:
        metrics = self._durability_metrics(records.values())
        rows = tuple(records.values())
        return {
            "algorithm": ALGORITHM,
            "minimum_observations": MIN_CLUSTER_OBSERVATIONS,
            "allowance_percent": allowance_percent(allowance),
            "eligible_symbol_route_histories": eligible_history_count,
            "formed_mrz_count": len(records),
            "formation_coverage": rate_payload(len(records), eligible_history_count),
            "route_breakdown": [
                {
                    "route": route.value,
                    **self._durability_metrics(
                        row for row in rows if row["route"] == route.value
                    ),
                }
                for route in (Route.BTD, Route.STR)
            ],
            **metrics,
        }

    def _durability_metrics(
        self,
        records: Iterable[Mapping[str, object]],
    ) -> dict[str, object]:
        rows = tuple(records)
        with_evidence = [
            row for row in rows if int(row["post_activation_observation_count"]) > 0
        ]
        completed = [row for row in rows if row["lifecycle"]["completed"]]
        pressured = [
            row
            for row in with_evidence
            if row["migration_pressure"]["status"]
            in {"UNDER_PRESSURE", "MIGRATION_CANDIDATE"}
        ]
        successor_pressure = [
            row
            for row in with_evidence
            if row["successor_watch"]["status"] == "SUCCESSOR_CANDIDATE"
        ]
        maintained = [
            row
            for row in with_evidence
            if row["route_integrity"]["status"] == "MAINTAINED"
        ]
        early = [row for row in completed if row["lifecycle"]["early_migration"]]
        resolved_cases = [
            row
            for row in rows
            if int(row["structural_response"]["resolved_outcome_count"]) > 0
        ]
        supportive_count = sum(
            int(row["structural_response"]["supportive_outcome_count"])
            for row in rows
        )
        adverse_count = sum(
            int(row["structural_response"]["adverse_outcome_count"])
            for row in rows
        )
        neutral_count = sum(
            int(row["structural_response"]["neutral_unresolved_outcome_count"])
            for row in rows
        )
        resolved_count = supportive_count + adverse_count
        early_adverse = [
            row for row in with_evidence if row["structural_response"]["early_adverse"]
        ]
        return {
            "formations_with_post_activation_evidence": len(with_evidence),
            "resolved_case_count": len(resolved_cases),
            "unresolved_case_count": len(rows) - len(resolved_cases),
            "supportive_outcome_count": supportive_count,
            "adverse_outcome_count": adverse_count,
            "neutral_unresolved_outcome_count": neutral_count,
            "resolved_outcome_count": resolved_count,
            "supportive_rate": rate_payload(supportive_count, resolved_count),
            "adverse_rate": rate_payload(adverse_count, resolved_count),
            "supportive_to_adverse_balance": f"{supportive_count} : {adverse_count}",
            "median_time_to_first_supportive_seconds": median_text(
                Decimal(str(row["structural_response"]["first_supportive"]["seconds_from_activation"]))
                for row in rows
                if row["structural_response"]["first_supportive"]["seconds_from_activation"]
                is not None
            ),
            "time_to_first_supportive_sample_count": sum(
                row["structural_response"]["first_supportive"]["seconds_from_activation"]
                is not None
                for row in rows
            ),
            "median_time_to_first_adverse_seconds": median_text(
                Decimal(str(row["structural_response"]["first_adverse"]["seconds_from_activation"]))
                for row in rows
                if row["structural_response"]["first_adverse"]["seconds_from_activation"]
                is not None
            ),
            "time_to_first_adverse_sample_count": sum(
                row["structural_response"]["first_adverse"]["seconds_from_activation"]
                is not None
                for row in rows
            ),
            "early_adverse_incidence": rate_payload(
                len(early_adverse),
                len(with_evidence),
            ),
            "early_adverse_window_observations": EARLY_BEHAVIOR_MAX_POST_ACTIVATION_OBSERVATIONS,
            "median_containment_percentage": median_text(
                Decimal(str(row["containment"]["percentage"]))
                for row in with_evidence
                if row["containment"]["percentage"] is not None
            ),
            "containment_sample_count": len(with_evidence),
            "median_observed_lifespan_seconds": median_text(
                Decimal(str(row["observed_lifespan_seconds"])) for row in rows
            ),
            "observed_lifespan_sample_count": len(rows),
            "completed_lifecycle_count": len(completed),
            "censored_lifecycle_count": len(rows) - len(completed),
            "median_time_to_migration_seconds": median_text(
                Decimal(str(row["lifecycle"]["time_to_migration_seconds"]))
                for row in completed
            ),
            "time_to_migration_sample_count": len(completed),
            "migration_pressure_incidence": rate_payload(
                len(pressured),
                len(with_evidence),
            ),
            "median_time_to_first_pressure_seconds": median_text(
                Decimal(str(row["migration_pressure"]["time_to_first_pressure_seconds"]))
                for row in pressured
                if row["migration_pressure"]["time_to_first_pressure_seconds"]
                is not None
            ),
            "time_to_first_pressure_sample_count": sum(
                row["migration_pressure"]["time_to_first_pressure_seconds"]
                is not None
                for row in pressured
            ),
            "migration_confirmation_incidence": rate_payload(
                len(completed),
                len(rows),
            ),
            "early_migration_incidence": rate_payload(len(early), len(rows)),
            "successor_pressure_incidence": rate_payload(
                len(successor_pressure),
                len(with_evidence),
            ),
            "route_integrity_maintained": rate_payload(
                len(maintained),
                len(with_evidence),
            ),
        }

    def _incremental_cohorts(
        self,
        records_by_allowance: Mapping[
            Decimal,
            Mapping[HistoryKey, Mapping[str, object]],
        ],
    ) -> list[dict[str, object]]:
        baseline_keys = set(records_by_allowance[POLICY_ALLOWANCES[0]])
        middle_keys = set(records_by_allowance[POLICY_ALLOWANCES[1]])
        wide_keys = set(records_by_allowance[POLICY_ALLOWANCES[2]])
        definitions = (
            (
                "BASELINE_1_00",
                "Baseline 1.00% cohort",
                "Forms at 1.00%",
                POLICY_ALLOWANCES[0],
                baseline_keys,
            ),
            (
                "INCREMENTAL_1_50",
                "Incremental 1.50% cohort",
                "Fails at 1.00% and forms at 1.50%",
                POLICY_ALLOWANCES[1],
                middle_keys - baseline_keys,
            ),
            (
                "INCREMENTAL_2_00",
                "Incremental 2.00% cohort",
                "Fails at 1.50% and forms at 2.00%",
                POLICY_ALLOWANCES[2],
                wide_keys - middle_keys,
            ),
        )
        cohorts = []
        for code, label, definition, allowance, keys in definitions:
            records = [records_by_allowance[allowance][key] for key in sorted(keys)]
            cohorts.append(
                {
                    "code": code,
                    "label": label,
                    "definition": definition,
                    "allowance_percent": allowance_percent(allowance),
                    "history_count": len(records),
                    "histories": [record["history_id"] for record in records],
                    **self._durability_metrics(records),
                }
            )
        return cohorts

    def _symbol_details(
        self,
        records_by_allowance: Mapping[
            Decimal,
            Mapping[HistoryKey, Mapping[str, object]],
        ],
    ) -> list[dict[str, object]]:
        keys = sorted(
            set().union(*(set(records) for records in records_by_allowance.values())),
            key=lambda key: (key[0], key[1].value),
        )
        return [
            {
                "history_id": _history_id(key),
                "symbol": key[0],
                "route": key[1].value,
                "policies": [
                    (
                        records_by_allowance[allowance][key]
                        if key in records_by_allowance[allowance]
                        else {
                            "history_id": _history_id(key),
                            "symbol": key[0],
                            "route": key[1].value,
                            "formation_policy": {
                                "algorithm": ALGORITHM,
                                "minimum_observations": MIN_CLUSTER_OBSERVATIONS,
                                "allowance_percent": allowance_percent(allowance),
                            },
                            "formed": False,
                        }
                    )
                    for allowance in POLICY_ALLOWANCES
                ],
            }
            for key in keys
        ]

    def _migration_pressure_summary(
        self,
        records: Mapping[HistoryKey, Mapping[str, object]],
    ) -> dict[str, object]:
        statuses = Counter(
            str(record["migration_pressure"]["status"])
            for record in records.values()
        )
        successors = Counter(
            str(record["successor_watch"]["status"])
            for record in records.values()
        )
        return {
            "formed_mrz_count": len(records),
            "stable": statuses["STABLE"],
            "under_pressure": statuses["UNDER_PRESSURE"],
            "migration_candidate": statuses["MIGRATION_CANDIDATE"],
            "not_yet_assessable": statuses["NO_EVIDENCE"],
            "successor_watch": {
                "no_successor": successors["NO_SUCCESSOR_CANDIDATE"],
                "external_observations": successors["EXTERNAL_OBSERVATIONS"],
                "no_qualifying_successor": successors["NO_QUALIFYING_SUCCESSOR"],
                "candidate_detected": successors["SUCCESSOR_CANDIDATE"],
            },
        }

    @staticmethod
    def _evidence_interpretation(
        eligible_history_count: int,
        policy_summaries: Sequence[Mapping[str, object]],
        cohorts: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        baseline = policy_summaries[0]
        baseline_cohort = cohorts[0]
        middle = cohorts[1]
        wide = cohorts[2]
        preliminary = eligible_history_count < LOW_SAMPLE_SEQUENCE_THRESHOLD
        if preliminary:
            code = "PRELIMINARY_INSUFFICIENT"
            heading = "Evidence remains preliminary"
            text = (
                "The current sample does not yet support a reliable durability distinction "
                "between 1.00%, 1.50%, and 2.00%. Formation selectivity and resolved "
                "route-supportive versus route-adverse outcomes remain visible below."
            )
        elif middle["history_count"] == 0 and wide["history_count"] == 0:
            code = "NO_INCREMENTAL_FORMATIONS"
            heading = "No incremental cohort observed"
            text = (
                "The wider allowances admitted no additional symbol-route histories in "
                "the current sample. No durability distinction is available."
            )
        else:
            cohort_rates = [
                (
                    cohort,
                    Decimal(str(cohort["supportive_rate"]["percentage"]))
                    if cohort["supportive_rate"]["percentage"] is not None
                    else None,
                )
                for cohort in (baseline_cohort, middle, wide)
            ]
            resolved_rates = [(cohort, rate) for cohort, rate in cohort_rates if rate is not None]
            baseline_rate = cohort_rates[0][1]
            incremental_rates = [rate for _cohort, rate in cohort_rates[1:] if rate is not None]
            code = "OBSERVED_INCREMENTAL_COHORTS"
            if not resolved_rates:
                heading = "Durability outcomes remain unresolved"
                text = (
                    "Additional formations are present, but no route-supportive or "
                    "route-adverse post-activation outcomes are resolved yet."
                )
            elif baseline_rate is not None and incremental_rates and all(
                baseline_rate > rate for rate in incremental_rates
            ):
                heading = "Baseline route-supportive rate is currently higher"
                text = (
                    "The 1.00% baseline formed fewer MRZs than the wider policies and its "
                    "resolved post-activation outcomes currently show a higher "
                    "route-supportive rate than each resolved incremental cohort."
                )
            elif baseline_rate is not None and incremental_rates and any(
                rate >= baseline_rate for rate in incremental_rates
            ):
                heading = "Additional formations preserve current route-role evidence"
                text = (
                    "At least one wider-policy incremental cohort currently matches or "
                    "exceeds the 1.00% baseline route-supportive rate. The present evidence "
                    "does not show that tighter selectivity alone buys greater durability."
                )
            else:
                heading = "Selectivity and durability remain only partly resolved"
                text = (
                    "The current cohorts do not yet provide comparable resolved "
                    "route-supportive and route-adverse evidence across all allowances."
                )
        return {
            "code": code,
            "heading": heading,
            "text": text,
            "facts": [
                (
                    f"1.00% formed {baseline['formed_mrz_count']} of "
                    f"{baseline['eligible_symbol_route_histories']} eligible histories."
                ),
                f"1.50% admitted {middle['history_count']} incremental histories.",
                f"2.00% admitted {wide['history_count']} incremental histories.",
                (
                    f"1.00% baseline resolved outcomes: "
                    f"{baseline_cohort['supportive_outcome_count']} supportive and "
                    f"{baseline_cohort['adverse_outcome_count']} adverse."
                ),
                (
                    f"Incremental 1.50% resolved outcomes: "
                    f"{middle['supportive_outcome_count']} supportive and "
                    f"{middle['adverse_outcome_count']} adverse."
                ),
                (
                    f"Incremental 2.00% resolved outcomes: "
                    f"{wide['supportive_outcome_count']} supportive and "
                    f"{wide['adverse_outcome_count']} adverse."
                ),
            ],
            "production_recommendation": None,
        }
