from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.responses import JSONResponse, PlainTextResponse, Response

log = logging.getLogger("bot_factory")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

def env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

app = FastAPI(title="BOT_FACTORY", version="1.0.0")

@app.on_event("startup")
async def _startup() -> None:
    # Best-effort init of PTB handlers (doesn't crash startup)
    try:
        from app.bot.investor_wallet_bot import initialize_bot  # type: ignore
        initialize_bot()
        log.info("telegram bot initialized")
    except Exception:
        log.exception("telegram bot init failed (non-fatal)")

@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"

@app.get("/ready", response_class=PlainTextResponse)
async def ready() -> str:
    return "ok"

@app.get("/status")
async def status() -> dict:
    return {
        "ok": True,
        "bot_token_present": bool(env_str("BOT_TOKEN")),
        "database_url_present": bool(env_str("DATABASE_URL")),
        "telegram_webhook_secret_present": bool(env_str("TELEGRAM_WEBHOOK_SECRET")),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT"),
        "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
        "railway_project": os.getenv("RAILWAY_PROJECT_NAME"),
        "git_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA"),
    }

@app.get("/debug/telegram")
async def debug_telegram() -> dict:
    token = env_str("BOT_TOKEN")
    if not token:
        return {"ok": True, "bot_token_present": False}

    err = None
    info_dict = None

    try:
        from telegram import Bot  # type: ignore
        b = Bot(token=token)  # PTB v20+ async
        info = await b.get_webhook_info()
        # PTB returns WebhookInfo dataclass-like with to_dict() in many versions;
        # fall back to __dict__ if missing
        if hasattr(info, "to_dict"):
            info_dict = info.to_dict()
        else:
            info_dict = getattr(info, "__dict__", None)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log.exception("debug_telegram failed")

    return {
        "ok": True,
        "bot_token_present": True,
        "webhook_info": info_dict,
        "error": err,
    }

@app.get("/debug/webhook")
async def debug_webhook(request: Request) -> dict:
    """
    Shows whether the incoming header matches TELEGRAM_WEBHOOK_SECRET (without leaking it).
    Useful to debug 401 issues through Railway edge.
    """
    expected = env_str("TELEGRAM_WEBHOOK_SECRET") or ""
    got = (request.headers.get("x-telegram-bot-api-secret-token") or "").strip()

    return {
        "ok": True,
        "expected_present": bool(expected),
        "header_present": bool(got),
        "match": bool(expected) and hmac.compare_digest(got, expected),
        "expected_sha256_8": sha256_hex(expected)[:8] if expected else None,
        "got_sha256_8": sha256_hex(got)[:8] if got else None,
    }

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    expected = env_str("TELEGRAM_WEBHOOK_SECRET")
    if expected:
        got = (request.headers.get("x-telegram-bot-api-secret-token") or "").strip()
        if not hmac.compare_digest(got, expected):
            # Intentionally 401 so we see it clearly in logs during setup
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        update_dict: Any = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    try:
        from app.bot.investor_wallet_bot import process_webhook  # type: ignore
        await process_webhook(update_dict)
    except Exception as e:
        # Return 200 to prevent Telegram retry storms, but log everything
        print(f"process_webhook failed: {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"ok": True, "error": "process_webhook_failed"}, status_code=200)

    return {"ok": True}

@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt() -> str:
    return "User-agent: *\nDisallow: /\n"

@app.get("/", include_in_schema=False)
def root():
    return HTMLResponse(
        "<h2>BOT_FACTORY</h2><ul>"
        "<li><a href='/docs'>/docs</a></li>"
        "<li><a href='/health'>/health</a></li>"
        "<li><a href='/ready'>/ready</a></li>"
        "<li><a href='/status'>/status</a></li>"
        "<li><a href='/debug/telegram'>/debug/telegram</a></li>"
        "<li><a href='/debug/webhook'>/debug/webhook</a></li>"
        "</ul>"
    )

@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)