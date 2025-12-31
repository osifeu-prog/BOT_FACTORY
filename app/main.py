from __future__ import annotations

import os
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

log = logging.getLogger("bot_factory")

# -------------------------
# ENV helpers (empty => None)
# -------------------------
def env_str(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def env_bool(name: str, default: bool = False) -> bool:
    v = env_str(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y", "on")

def env_csv(name: str) -> list[str] | None:
    v = env_str(name)
    if v is None:
        return None
    parts = [p.strip() for p in v.split(",")]
    parts = [p for p in parts if p]
    return parts if parts else None

BUILD_ID = env_str("BUILD_ID")
PUBLIC_BASE_URL = env_str("PUBLIC_BASE_URL")  # optional
DOCS_RATE_LIMIT = env_str("DOCS_RATE_LIMIT")  # optional, handled later if you add middleware

# Security-related optional envs (can be empty in Railway => treated as None/False)
ADMIN_API_KEY = env_str("ADMIN_API_KEY")  # recommended
ADMIN_ALLOW_IPS = env_csv("ADMIN_ALLOW_IPS")  # optional
TRUST_CLOUDFLARE = env_bool("TRUST_CLOUDFLARE", default=False)  # optional
CF_IP_ALLOW = env_csv("CF_IP_ALLOW")  # optional

# -------------------------
# App: define FIRST, with health endpoint that never imports DB/Telegram
# -------------------------
app = FastAPI(
    title="BOT_FACTORY",
    version=BUILD_ID or "dev",
)


@app.get("/robots.txt", response_class=PlainTextResponse)`nasync def robots_txt():`n    return "User-agent: *\nDisallow: /\n"`n
@app.get("/health")
def health() -> dict[str, Any]:
    # Must never touch DB/Telegram. Only return cheap info.
    return {
        "ok": True,
        "build_id": BUILD_ID,
        "has_bot_token": bool(env_str("BOT_TOKEN")),
        "has_database_url": bool(env_str("DATABASE_URL")),
    }

# -------------------------
# Lazy-init state (never block startup)
# -------------------------
_BOOT = {
    "bot_initialized": False,
    "db_ready": False,
    "errors": [],
}

def _record_error(where: str, e: Exception) -> None:
    msg = f"{where}: {type(e).__name__}: {e}"
    _BOOT["errors"].append(msg)
    log.exception(msg)

@app.get("/status")
def status() -> dict[str, Any]:
    # Optional debug endpoint (safe). You can protect later.
    return dict(_BOOT)

@app.on_event("startup")
def _startup_best_effort() -> None:
    """
    Best-effort init only.
    Never crash startup because Railway healthcheck must pass even when env/DB is missing.
    """
    # 1) DB bootstrap (optional)
    try:
        dburl = env_str("DATABASE_URL")
        if dburl:
            from app.core.telegram_updates import ensure_telegram_updates_table  # lazy import
            ensure_telegram_updates_table()
            _BOOT["db_ready"] = True
    except Exception as e:
        _record_error("db_init", e)

    # 2) Telegram bot init (optional)
    try:
        token = env_str("BOT_TOKEN")
        if token:
            initialize_bot()
            _BOOT["bot_initialized"] = True
    except Exception as e:
        _record_error("bot_init", e)

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """
    Webhook must never crash the app.
    If bot isn't configured/initialized, return 200 to avoid Telegram retry storms,
    but include ok=false in body + log.
    """
    try:
        update_dict = await request.json()
    except Exception as e:
        _record_error("webhook_parse_json", e)
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=200)

    # Optional dedupe: best-effort only (never crash)
    try:
        from app.core.telegram_updates import register_update_once  # lazy import
        if not register_update_once(update_dict):
            return JSONResponse({"ok": True, "deduped": True}, status_code=200)
    except Exception as e:
        _record_error("dedupe", e)

    # If bot token missing or bot not initialized, do not crash.
    if not env_str("BOT_TOKEN"):
        return JSONResponse({"ok": False, "reason": "BOT_TOKEN_missing"}, status_code=200)

    try:
        await process_webhook(update_dict)
        return JSONResponse({"ok": True}, status_code=200)
    except Exception as e:
        _record_error("process_webhook", e)
        # Still return 200 to avoid Telegram storm; log already captured
        return JSONResponse({"ok": False, "reason": "process_failed"}, status_code=200)