from __future__ import annotations

import hmac
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app.activation_feasibility import ActivationFeasibilityService
from app.concentration import MIN_CLUSTER_OBSERVATIONS
from app.config import Settings
from app.logging_config import configure_logging
from app.mrz_robustness import MRZRobustnessService
from app.mrz_robustness_report import MRZRobustnessReportService
from app.repository import EdgeRepository, json_diagnostics, sanitize_payload
from app.validation import ObservationPayload


STATIC_DIR = Path(__file__).resolve().parent / "static"
LOGGER = logging.getLogger("edge2.api")


def supplied_secret(request: Request, payload: Any) -> str | None:
    header = request.headers.get("x-edge2-webhook-secret", "").strip()
    if header:
        return header
    authorization = request.headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if isinstance(payload, Mapping):
        value = payload.get("webhook_secret")
        return str(value).strip() if value is not None else None
    return None


def secret_is_valid(settings: Settings, request: Request, payload: Any) -> bool:
    if not settings.require_webhook_secret:
        return True
    if not settings.webhook_secret:
        return False
    candidate = supplied_secret(request, payload)
    return bool(candidate) and hmac.compare_digest(candidate, settings.webhook_secret)


def validation_diagnostics(exc: ValidationError) -> dict[str, Any]:
    errors = []
    for error in exc.errors(include_input=False, include_url=False):
        errors.append(
            {
                "location": [str(item) for item in error.get("loc", ())],
                "message": error.get("msg"),
                "type": error.get("type"),
            }
        )
    return {"errors": errors}


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()
    configure_logging(resolved.log_level)
    repository = EdgeRepository(resolved.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        LOGGER.info("EDGE 2.0 application started")
        yield
        LOGGER.info("EDGE 2.0 application stopped")

    application = FastAPI(
        title="EDGE 2.0",
        description="Operational SOURCE / ACTIVE MRZ state engine",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    application.state.settings = resolved
    application.state.repository = repository
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def symbol_lab() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get("/diagnostics/activation-feasibility", include_in_schema=False)
    def activation_feasibility_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "activation-feasibility.html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get("/diagnostics/mrz-robustness", include_in_schema=False)
    def mrz_robustness_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "mrz-robustness.html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get("/diagnostics/mrz-robustness-report", include_in_schema=False)
    def mrz_robustness_report_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "mrz-robustness-report.html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get(
        "/diagnostics/trading-window-feasibility",
        include_in_schema=False,
    )
    def trading_window_feasibility_page() -> FileResponse:
        return FileResponse(
            STATIC_DIR / "feasibility.html",
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @application.get("/health")
    def health() -> JSONResponse:
        try:
            return JSONResponse(repository.health())
        except Exception:
            LOGGER.exception("Health check failed")
            return JSONResponse(
                {
                    "status": "unhealthy",
                    "application": "ok",
                    "database": "unavailable",
                    "schema_version": "4.3",
                },
                status_code=503,
            )

    @application.post("/webhook/tradingview")
    async def tradingview_webhook(request: Request) -> JSONResponse:
        raw_body = await request.body()
        if len(raw_body) > resolved.max_request_bytes:
            record_rejection(
                repository,
                raw_body=raw_body,
                event_id=None,
                reason_code="payload_too_large",
                diagnostics={"maximum_bytes": resolved.max_request_bytes},
                sanitized_payload=None,
            )
            return JSONResponse({"ok": False, "error": "payload_too_large"}, status_code=413)

        try:
            raw_payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            record_rejection(
                repository,
                raw_body=raw_body,
                event_id=None,
                reason_code="invalid_json",
                diagnostics={"message": "Request body must be valid JSON"},
                sanitized_payload=None,
            )
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

        sanitized = sanitize_payload(raw_payload)
        event_id = str(raw_payload.get("event_id") or "").strip() if isinstance(raw_payload, dict) else None
        if not secret_is_valid(resolved, request, raw_payload):
            record_rejection(
                repository,
                raw_body=raw_body,
                event_id=event_id or None,
                reason_code="authentication_failed",
                diagnostics={"message": "Webhook authentication failed"},
                sanitized_payload=sanitized,
            )
            return JSONResponse({"ok": False, "error": "authentication_failed"}, status_code=401)

        try:
            payload = ObservationPayload.model_validate(raw_payload)
        except ValidationError as exc:
            record_rejection(
                repository,
                raw_body=raw_body,
                event_id=event_id or None,
                reason_code="schema_validation_failed",
                diagnostics=validation_diagnostics(exc),
                sanitized_payload=sanitized,
            )
            return JSONResponse(
                {
                    "ok": False,
                    "error": "schema_validation_failed",
                    **validation_diagnostics(exc),
                },
                status_code=400,
            )

        try:
            outcome = repository.ingest(payload, payload.price_tick(resolved.symbol_ticks))
        except Exception:
            LOGGER.exception(
                "Webhook processing failed",
                extra={"event_id": payload.event_id, "symbol": payload.symbol},
            )
            record_rejection(
                repository,
                raw_body=raw_body,
                event_id=payload.event_id,
                reason_code="processing_failed",
                diagnostics={"message": "Validated packet could not be processed atomically"},
                sanitized_payload=sanitized,
            )
            return JSONResponse({"ok": False, "error": "processing_failed"}, status_code=500)

        if outcome.duplicate:
            LOGGER.info(
                "Duplicate webhook ignored",
                extra={"event_id": outcome.event_id, "symbol": outcome.symbol},
            )
            return JSONResponse(
                {
                    "ok": True,
                    "accepted": False,
                    "duplicate": True,
                    "event_id": outcome.event_id,
                    "symbol": outcome.symbol,
                }
            )

        for transition in outcome.triggered_transitions:
            log_transition(transition)
        detail = repository.symbol_detail(outcome.symbol)
        LOGGER.info(
            "Webhook accepted",
            extra={"event_id": outcome.event_id, "symbol": outcome.symbol},
        )
        return JSONResponse(
            {
                "ok": True,
                "accepted": True,
                "duplicate": False,
                "event_id": outcome.event_id,
                "symbol": outcome.symbol,
                "state": detail,
            },
            status_code=201,
        )

    @application.get("/api/symbols")
    def symbols() -> dict[str, Any]:
        return {
            "minimum_cluster_observations": MIN_CLUSTER_OBSERVATIONS,
            "symbols": repository.symbols(),
        }

    @application.get("/api/diagnostics/activation-feasibility")
    def activation_feasibility() -> JSONResponse:
        service = ActivationFeasibilityService(repository.schema_43_observations)
        return JSONResponse(
            service.generate_report(),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @application.get("/api/diagnostics/mrz-robustness")
    def mrz_robustness() -> JSONResponse:
        service = MRZRobustnessService(repository.mrz_robustness_inputs)
        return JSONResponse(
            service.generate_report(),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @application.get("/api/diagnostics/mrz-robustness-report")
    def mrz_robustness_report() -> JSONResponse:
        service = MRZRobustnessReportService(repository.schema_43_observations)
        return JSONResponse(
            service.generate_report(),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @application.get("/api/diagnostics/trading-window-feasibility")
    def trading_window_feasibility() -> JSONResponse:
        return JSONResponse(
            repository.trading_window_feasibility_report(),
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @application.get("/api/symbols/{symbol}")
    def symbol_detail(symbol: str) -> dict[str, Any]:
        try:
            detail = repository.symbol_detail(symbol)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if detail is None:
            raise HTTPException(status_code=404, detail="symbol_not_found")
        return detail

    @application.get("/api/symbols/{symbol}/mrz")
    def symbol_mrz(symbol: str) -> dict[str, Any]:
        return symbol_detail(symbol)

    return application


def record_rejection(repository: EdgeRepository, **kwargs: Any) -> None:
    try:
        repository.record_rejection(**kwargs)
    except Exception:
        LOGGER.exception("Unable to persist ingestion rejection")
    LOGGER.warning(
        "Webhook rejected",
        extra={
            "event_id": kwargs.get("event_id"),
            "reason_code": kwargs.get("reason_code"),
        },
    )


def log_transition(transition: Any) -> None:
    old = transition.old_mrz
    new = transition.new_mrz
    LOGGER.info(
        transition.event_type.value,
        extra={
            "event_type": transition.event_type.value,
            "event_id": transition.trigger_event_id,
            "symbol": transition.symbol,
            "route_owner": transition.route_owner.value,
            "old_core_mrz_lower": str(old.core_mrz_lower) if old else None,
            "old_core_mrz_upper": str(old.core_mrz_upper) if old else None,
            "core_mrz_lower": str(new.core_mrz_lower),
            "core_mrz_upper": str(new.core_mrz_upper),
        },
    )
