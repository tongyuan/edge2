from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    if os.getenv("APP_ENV", "development").strip().lower() in {"production", "staging"}:
        return
    for path in (ROOT_DIR / ".env.local", ROOT_DIR / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_symbol_ticks(raw: str) -> dict[str, Decimal]:
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("EDGE2_SYMBOL_TICKS_JSON must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("EDGE2_SYMBOL_TICKS_JSON must be a JSON object")
    ticks: dict[str, Decimal] = {}
    for symbol, value in payload.items():
        try:
            tick = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid tick for {symbol}") from exc
        if not tick.is_finite() or tick <= 0:
            raise ValueError(f"Tick for {symbol} must be finite and positive")
        ticks[str(symbol).strip().upper()] = tick
    return ticks


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    database_url: str
    webhook_secret: str | None
    require_webhook_secret: bool
    symbol_ticks: dict[str, Decimal]
    max_request_bytes: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_local_env()
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        secret = os.getenv("WEBHOOK_SECRET", "").strip() or None
        require_secret = env_bool("REQUIRE_WEBHOOK_SECRET", True)
        if app_env == "production" and require_secret and not secret:
            raise ValueError("WEBHOOK_SECRET is required in production")
        return cls(
            app_env=app_env,
            database_url=database_url,
            webhook_secret=secret,
            require_webhook_secret=require_secret,
            symbol_ticks=parse_symbol_ticks(os.getenv("EDGE2_SYMBOL_TICKS_JSON", "")),
            max_request_bytes=int(os.getenv("MAX_REQUEST_BYTES", "32768")),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        )
