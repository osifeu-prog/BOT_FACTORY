import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.database import init_db
from app.bot.investor_wallet_bot import initialize_bot, process_webhook
from app.monitoring import run_selftest

BUILD_ID = os.getenv("BUILD_ID", "local-dev")

log = logging.getLogger("slhnet")

app = FastAPI(title="SLH Investor Gateway")


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
            return (chat.get("type") == "private")

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = (m2.get("chat") or {}) if isinstance(m2, dict) else {}
            return (chat.get("type") == "private")

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


@app.on_event("startup")
async def startup_event():
    init_db()
    await initialize_bot()


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

    if not _slh_is_private_update(update_dict):
        chat_type, chat_id = _slh_chat_fingerprint(update_dict)
        update_id = str(update_dict.get("update_id") or "?")
        try:
            log.info(
                f"SLH SAFETY: ignored non-private update_id={update_id} chat_type={chat_type} chat_id={chat_id}"
            )
        except Exception:
            pass
        return JSONResponse(
            {"ok": True, "ignored": "non-private", "chat_type": chat_type, "chat_id": chat_id},
            status_code=status.HTTP_200_OK,
        )

    await process_webhook(update_dict)
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)
