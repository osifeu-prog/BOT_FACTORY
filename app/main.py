
# --- SLH SAFETY: ignore non-private updates at webhook (groups/channels) ---
def _slh_is_private_update(payload: dict) -> bool:
    try:
        msg = payload.get("message") or payload.get("edited_message") or payload.get("channel_post") or payload.get("edited_channel_post")
        if isinstance(msg, dict):
            chat = msg.get("chat") or {}
            return chat.get("type") == "private"

        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            m2 = cb.get("message") or {}
            chat = m2.get("chat") or {}
            return chat.get("type") == "private"

        # If we cannot detect chat type, do not block.
        return True
    except Exception:
        return True
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.database import init_db
from app.bot.investor_wallet_bot import initialize_bot, process_webhook
from app.monitoring import run_selftest

app = FastAPI(title="SLH Investor Gateway")


@app.on_event("startup")
async def startup_event():
    """
    أ—آ¨أ—آ¥ أ—آ¤أ—آ¢أ—â€Œ أ—ع¯أ—â€”أ—ع¾ أ—â€؛أ—ع¯أ—آ©أ—آ¨ أ—â€‌أ—آ©أ—آ¨أ—ع¾ أ—آ¢أ—â€¢أ—إ“أ—â€‌:
    1. أ—â€چأ—â€¢أ—â€¢أ—â€œأ—ع¯ أ—آ©أ—â€‌أ—ع©أ—â€کأ—إ“أ—ع¯أ—â€¢أ—ع¾ (users, transactions) أ—آ§أ—â„¢أ—â„¢أ—â€چأ—â€¢أ—ع¾.
    2. أ—â€چأ—ع¯أ—ع¾أ—â€”أ—إ“ أ—ع¯أ—ع¾ أ—â€کأ—â€¢أ—ع© أ—â€‌أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ أ—â€¢أ—آ§أ—â€¢أ—â€کأ—آ¢ webhook.
    """
    init_db()
    await initialize_bot()


@app.get("/")
async def root():
    return {"message": "SLH Investor Gateway is running"}


@app.get("/health")
async def health():
    """
    أ—â€چأ—طŒأ—إ“أ—â€¢أ—إ“ healthcheck أ—â€کأ—طŒأ—â„¢أ—طŒأ—â„¢ أ—إ“أ—آ¨أ—â„¢أ—â„¢أ—إ“أ—â€¢أ—â€¢أ—â„¢.
    """
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """
    أ—â€کأ—â€œأ—â„¢أ—آ§أ—ع¾ أ—â€چأ—â€¢أ—â€؛أ—آ أ—â€¢أ—ع¾ أ—â€چأ—â€‌أ—â„¢أ—آ¨أ—â€‌:
    - DB
    - ENV
    - أ—ع©أ—â€¢أ—آ§أ—ع؛ أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ أ—آ§أ—â„¢أ—â„¢أ—â€Œ
    (أ—â€کأ—إ“أ—â„¢ getMe, أ—â€؛أ—â€œأ—â„¢ أ—آ©أ—â„¢أ—â€‌أ—â„¢أ—â€‌ أ—â€چأ—â€‌أ—â„¢أ—آ¨ أ—â€¢أ—آ§أ—إ“ أ—إ“أ—آ أ—â„¢أ—ع©أ—â€¢أ—آ¨).
    """
    result = run_selftest(quick=True)
    return {"status": result["status"], "checks": result["checks"]}


@app.get("/selftest")
async def selftest():
    """
    أ—â€کأ—â€œأ—â„¢أ—آ§أ—â€‌ أ—آ¢أ—â€چأ—â€¢أ—آ§أ—â€‌: DB, ENV, Telegram, BSC.
    أ—ع¯أ—آ¤أ—آ©أ—آ¨ أ—إ“أ—آ¤أ—ع¾أ—â€¢أ—â€” أ—â€کأ—â€œأ—آ¤أ—â€œأ—آ¤أ—ع؛ أ—إ“أ—آ§أ—â€کأ—إ“ أ—â€œأ—â€¢"أ—â€”.
    """
    return run_selftest(quick=False)


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    أ—آ أ—آ§أ—â€¢أ—â€œأ—ع¾ أ—â€‌-webhook أ—آ©أ—إ“ أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ.
    أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ أ—آ©أ—â€¢أ—إ“أ—â€” أ—إ“أ—â€؛أ—ع¯أ—ع؛ أ—آ¢أ—â€œأ—â€؛أ—â€¢أ—آ أ—â„¢أ—â€Œ, أ—â€¢أ—ع¯أ—آ أ—â€”أ—آ أ—â€¢ أ—â€چأ—آ¢أ—â€کأ—â„¢أ—آ¨أ—â„¢أ—â€Œ أ—ع¯أ—â€¢أ—ع¾أ—â€Œ أ—إ“-process_webhook.
    """
    update_dict = await request.json()
    # SLH SAFETY: ignore groups/channels
    if not _slh_is_private_update(payload if 'payload' in locals() else data if 'data' in locals() else update if 'update' in locals() else locals().get('update_json', {})):
        _p = payload if 'payload' in locals() else data if 'data' in locals() else update if 'update' in locals() else locals().get('update_json', {})
        _t,_cid = _slh_chat_fingerprint(_p)
        _uid = str((_p.get('update_id') if isinstance(_p, dict) else None) or '?')
        try:
            import logging as _logging
            _logging.getLogger('slhnet').info(f'SLH SAFETY: ignored non-private update update_id={_uid} chat_type={_t} chat_id={_cid}')
        except Exception:
            pass
        return { "ok": True, "ignored": "non-private", "chat_type": _t }
    # SLH SAFETY: ignore groups/channels
    if not _slh_is_private_update(payload if 'payload' in locals() else data if 'data' in locals() else update if 'update' in locals() else locals().get('update_json', {})):
        return { "ok": True, "ignored": "non-private" }
    await process_webhook(update_dict)
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)
