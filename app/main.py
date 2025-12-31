import os, logging
logger = logging.getLogger(__name__)
logger.warning("BOOT_MARKER: BOT_FACTORY main.py loaded - BUILD_ID=%s", os.getenv("BUILD_ID"))
import os
import logging
logger = logging.getLogger(__name__)
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.database import init_db
from app.core.telegram_updates import ensure_telegram_updates_table, register_update_once
from app.core.ledger import ensure_ledger_tables
from app.bot.investor_wallet_bot import initialize_bot, process_webhook
from app.monitoring import run_selftest

BUILD_ID = os.getenv("BUILD_ID", "local-dev")
log = logging.getLogger("slhnet")
from app.routers.investments import router as invest_router

app = FastAPI(title="SLH Investor Gateway")




@app.get("/version")
def version():
    return {
        "railway_git_commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA"),
        "railway_git_branch": os.getenv("RAILWAY_GIT_BRANCH"),
        "railway_service": os.getenv("RAILWAY_SERVICE_NAME"),
    }

app.include_router(invest_router)
def _slh_is_private_update(payload: Dict[str, Any]) -> bool:
    try:
        msg = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
        )
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            return chat.get("type") == "private"

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = (m2.get("chat") or {}) if isinstance(m2, dict) else {}
            return chat.get("type") == "private"

        return True
    except Exception:
        return True


def _slh_chat_fingerprint(payload: Dict[str, Any]) -> Tuple[str, str]:
    try:
        msg = (
            payload.get("message")
            or payload.get("edited_message")
            or payload.get("channel_post")
            or payload.get("edited_channel_post")
        )
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            return str(chat.get("type") or "?"), str(chat.get("id") or "?")

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = (m2.get("chat") or {}) if isinstance(m2, dict) else {}
            return str(chat.get("type") or "?"), str(chat.get("id") or "?")

        return "?", "?"
    except Exception:
        return "?", "?"


def _truthy(v: str | None) -> bool:
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _bot_token_looks_valid(token: str) -> bool:
    t = (token or "").strip()
    if len(t) < 35 or ":" not in t:
        return False
    left, right = t.split(":", 1)
    return left.isdigit() and len(right) >= 20


@app.on_event("startup")
async def startup_event():
    init_db()
    ensure_telegram_updates_table()
    dsn = (os.getenv("DATABASE_URL") or "").strip().lower()
    if dsn.startswith("postgres://") or dsn.startswith("postgresql://") or dsn.startswith("postgres"):
        ensure_ledger_tables()
    if _truthy(os.getenv("DISABLE_TELEGRAM_BOT")):
        log.warning("Telegram bot disabled via DISABLE_TELEGRAM_BOT=1 -> starting API only")
        return

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token or not _bot_token_looks_valid(bot_token):
        log.warning("BOT_TOKEN missing/invalid -> starting API only")
        return

    try:
        await initialize_bot()
        log.info("Telegram bot initialized successfully")
    except Exception:
        log.exception("Telegram bot initialization failed -> starting API only")


@app.get("/")
async def root():
    return {"message": "SLH Investor Gateway is running", "build_id": BUILD_ID}


@app.get("/health")
async def health():
    return {"status": "ok", "build_id": BUILD_ID}


@app.get("/__whoami")
async def whoami(request: Request):
    now = datetime.now(timezone.utc).isoformat()
    env_keys = [
        "RAILWAY_ENVIRONMENT",
        "RAILWAY_PROJECT_ID",
        "RAILWAY_SERVICE_NAME",
        "RAILWAY_GIT_REPO_NAME",
        "RAILWAY_GIT_BRANCH",
        "RAILWAY_GIT_COMMIT_SHA",
        "PORT",
    ]
    env = {k: os.getenv(k) for k in env_keys if os.getenv(k) is not None}
    return {
        "ok": True,
        "time_utc": now,
        "build_id": BUILD_ID,
        "env": env,
        "client": {
            "ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    }


@app.get("/ready")
async def ready():
    result = run_selftest(quick=True)
    return {"status": result.get("status"), "checks": result.get("checks")}


@app.get("/selftest")
async def selftest():
    return run_selftest(quick=False)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    update_dict = await request.json()
    try:
        await process_webhook(update_dict)
    except Exception:
        logger.exception("telegram webhook processing failed")
        # أ—â€”أ—آ©أ—â€¢أ—â€ک: أ—â€چأ—â€”أ—â€“أ—â„¢أ—آ¨أ—â„¢أ—â€Œ 200 أ—â€؛أ—â€œأ—â„¢ أ—آ©أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ أ—إ“أ—ع¯ أ—â„¢أ—آ¢أ—آ©أ—â€‌ retry أ—ع¯أ—â„¢أ—آ أ—طŒأ—â€¢أ—آ¤أ—â„¢
        return {"ok": True}
    return {"ok": True}
