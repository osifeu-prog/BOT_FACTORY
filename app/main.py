import os
import logging
import json
from fastapi import FastAPI
import httpx
from fastapi import Request, BackgroundTasks

from app.api_core import router as core_router

log = logging.getLogger("bot_factory")

def _is_truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")

DISABLE_TELEGRAM = _is_truthy(os.getenv("DISABLE_TELEGRAM"))

app = FastAPI()
@app.get("/health")
def health():
    return {"ok": True}


from fastapi import Response, status
from sqlalchemy import text

@app.get("/ready")
def ready(response: Response):
    # Readiness: DB reachable
    try:
        # import inside handler so missing DATABASE_URL won't break import-time
        from app.db import ENGINE
        with ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "db": "up"}
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"ok": False, "db": "down", "error": str(e)[:200]}

app.include_router(core_router)


from fastapi import Request

@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    try:
        upd = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        upd = {}

    msg = (upd.get("message") or upd.get("edited_message") or {})
    text = (msg.get("text") or "").strip()
    chat = (msg.get("chat") or {})
    chat_id = chat.get("id")

    logging.getLogger("app").info("tg webhook: update_id=%s text=%s chat_id=%s",
                                  upd.get("update_id"), text[:50], chat_id)

    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")  # support both env names
    if token and chat_id and text:
        async def _send():
            try:
                if text.startswith("/start"):
                    reply = "✅ BOT_FACTORY online. (/start OK)"
                elif text.startswith("/chatid"):
                    reply = f"chat_id = {chat_id}"
                else:
                    reply = f"echo: {text}"

                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": reply}
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(url, json=payload)
            except Exception as e:
                logging.getLogger("app").exception("sendMessage failed: %s", str(e)[:200])

        background.add_task(_send)

    return {"ok": True}
@app.on_event("startup")
async def startup():
    if DISABLE_TELEGRAM:
        log.info("telegram disabled (DISABLE_TELEGRAM=1)")
        return

    # Import only when enabled so BOT_TOKEN isn't required when disabled
    from app.bot.investor_wallet_bot import ensure_handlers
    ensure_handlers()
    log.info("telegram bot initialized")
