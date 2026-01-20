from __future__ import annotations

import asyncio
import hmac
import os
import sys
import traceback
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.responses import JSONResponse, PlainTextResponse, Response


def env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _client_ip(request: Request) -> str:
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


app = FastAPI(title="BOT_FACTORY", version="1.0.0")


# -----------------------
# Health / Ready (PlainText) - never depends on DB/Telegram
# -----------------------
@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"


@app.get("/ready", response_class=PlainTextResponse)
async def ready() -> str:
    return "ok"


# -----------------------
# Status (JSON)
# -----------------------
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


# -----------------------
# Debug Telegram (lazy)
# -----------------------
@app.get("/debug/telegram")
async def debug_telegram() -> dict:
    token_present = bool(env_str("BOT_TOKEN"))
    info = None
    err = None

    if token_present:
        try:
            from telegram import Bot  # type: ignore

            token = env_str("BOT_TOKEN")
            b = Bot(token=token)  # type: ignore[arg-type]
            info = await asyncio.to_thread(b.get_webhook_info)
        except Exception as e:
            err = str(e)

    return {
        "ok": True,
        "bot_token_present": token_present,
        "webhook_info": (info.to_dict() if info else None),
        "error": err,
    }


# -----------------------
# Telegram Webhook (lazy import per-request)
# -----------------------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    # Optional Telegram secret-token header validation
    expected = (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()
    if expected:
        got = (request.headers.get("x-telegram-bot-api-secret-token") or "").strip()
        if (not got) or (not hmac.compare_digest(got, expected)):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        update_dict: Any = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    try:
        # Change this import to your real bot entry if needed:
        # from app.bot.investor_wallet_bot import process_webhook
        from app.bot.investor_wallet_bot import process_webhook  # type: ignore
        await process_webhook(update_dict)
    except Exception as e:
        # Never crash server; return ok to avoid Telegram retry storm
        print(f"process_webhook failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"ok": True, "error": "process_webhook_failed"}, status_code=200)

    return {"ok": True}


# -----------------------
# Noise reducers
# -----------------------
@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt() -> str:
    return "User-agent: *\nDisallow: /\n"


# -----------------------
# Simple root (no 404 noise)
# -----------------------
@app.get("/", include_in_schema=False)
def root():
    return HTMLResponse(
        "<h2>BOT_FACTORY</h2><ul>"
        "<li><a href='/docs'>/docs</a></li>"
        "<li><a href='/health'>/health</a></li>"
        "<li><a href='/ready'>/ready</a></li>"
        "<li><a href='/status'>/status</a></li>"
        "<li><a href='/debug/telegram'>/debug/telegram</a></li>"
        "</ul>"
    )


@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)