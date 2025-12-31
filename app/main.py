from __future__ import annotations

import os
import sys
import traceback
import asyncio
from typing import Any

from fastapi import FastAPI, Request
from starlette.responses import PlainTextResponse, JSONResponse

# -----------------------
# Helpers (safe env)
# -----------------------
def env_str(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def _client_ip(request: Request) -> str:
    # Minimal. If behind CF/proxy and you later want trust logic, add it here.
    xf = request.headers.get("x-forwarded-for")
    if xf:
        return xf.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"

# -----------------------
# App
# -----------------------
app = FastAPI()

# -----------------------
# Noise reducers
# -----------------------
@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nDisallow: /\n"

# -----------------------
# Health / Status (never depends on DB/Telegram)
# -----------------------
@app.get("/health")
async def health():
    # Don't touch DB/Telegram here. Just confirm process is alive.
    return {"ok": True}

@app.get("/status")
async def status():
    # Light visibility only; still no hard deps.
    # If you want later: expose bot/db readiness flags here.
    return {
        "ok": True,
        "bot_token_present": bool(env_str("BOT_TOKEN")),
        "database_url_present": bool(env_str("DATABASE_URL")),
    }

# -----------------------
# Debug Telegram (LAZY import)
# -----------------------
@app.get("/debug/telegram")
async def debug_telegram():
    token_present = bool(env_str("BOT_TOKEN"))
    info = None
    err = None

    if token_present:
        try:
            # Lazy import - must never break startup if telegram libs mismatch
            from telegram import Bot  # type: ignore
            b = Bot(token=env_str("BOT_TOKEN"))
            # run blocking call in a thread
            info = await asyncio.to_thread(b.get_webhook_info)
        except Exception as e:
            err = str(e)

    return {
        "bot_token_present": token_present,
        "webhook_info": (info.to_dict() if info else None),
        "error": err,
    }

# -----------------------
# Telegram Webhook (LAZY import per-request)
# -----------------------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    try:
        update_dict: Any = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)

    try:
        # LAZY import so a broken bot file doesn't kill the server
        from app.bot.investor_wallet_bot import process_webhook  # type: ignore
        await process_webhook(update_dict)
    except Exception as e:
        # Never crash server; return ok to avoid Telegram retry storm, log for debugging
        print(f"process_webhook: {e}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"ok": True, "error": "process_webhook_failed"}, status_code=200)

    return {"ok": True}