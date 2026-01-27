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
        update = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        update = {}

    msg = _extract_message(update)
    chat_id = _chat_id(msg)
    user_id = _from_id(msg) or msg.get("_callback_from_id")
    text = _text_or_callback(msg)

    log = logging.getLogger("app")
    log.info("tg webhook: update_id=%s text=%s chat_id=%s user_id=%s",
             update.get("update_id"), (text or "")[:60], chat_id, user_id)

    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
    redis_client = _get_redis_client(request)

    # redis_client may live on request.app.state; keep webhook resilient if missing
    redis_client = None
    try:
        redis_client = getattr(getattr(request, "app", None), "state", None)
        redis_client = getattr(redis_client, "redis_client", None)
    except Exception:
        redis_client = None

    if not (token and chat_id):
        return {"ok": True}

    async def _handle():
        try:
            uid = int(user_id or 0)

            # pending admin password flow (after clicking Admin Login)
            if uid and await _has_pending_login(redis_client, uid) and text and not text.startswith("admin:") and not text.startswith("public:"):
                await _clear_pending_login(redis_client, uid)

                need = (os.getenv("ADMIN_PASSWORD") or "").strip()
                if not need:
                    await _tg_send(token, chat_id, "❌ ADMIN_PASSWORD לא מוגדר בשרת.")
                    return

                if text.strip() == need:
                    ok = await _grant_admin(redis_client, uid)
                    if ok:
                        await _tg_send(token, chat_id, "✅ התחברת כאדמין.\nבחר פעולה:", _admin_menu())
                    else:
                        await _tg_send(token, chat_id, "❌ לא ניתן לשמור סשן אדמין (Redis).")
                else:
                    await _tg_send(token, chat_id, "❌ סיסמה שגויה. לחץ שוב Admin Login כדי לנסות מחדש.")
                return

            # /start -> buttons
            if text.startswith("/start"):
                await _tg_send(token, chat_id, "✅ BOT_FACTORY online.\nבחר פעולה:", _start_menu())
                return

            # keep /chatid too
            if text.startswith("/chatid"):
                await _tg_send(token, chat_id, f"chat_id={chat_id}\nuser_id={uid}")
                return

            # public button
            if text == "public:chatid":
                await _tg_send(token, chat_id, f"chat_id={chat_id}\nuser_id={uid}")
                return

            # admin login button
            if text == "admin:login":
                # Require Redis for login/session; otherwise user will be stuck
                if not await _redis_healthcheck(redis_client):
                    await _tg_send(token, chat_id, "⚠️ Redis לא מחובר/לא נגיש כרגע. לא ניתן לבצע Admin Login.\nבדוק ש-REDIS_URL קיים ושאתחול Redis הצליח בלוגים.")
                    return

                if uid and await _is_admin(redis_client, uid):
                    await _tg_send(token, chat_id, "✅ כבר מחובר כאדמין.\nבחר פעולה:", _admin_menu())
                    return

                await _set_pending_login(redis_client, uid)
                await _tg_send(
                    token,
                    chat_id,
                    "הכנס סיסמת אדמין (Reply להודעה הזו):",
                    {"force_reply": True, "selective": True},
                )
                return

            # admin actions (only if logged in)
            if text.startswith("admin:"):
                if not (uid and await _is_admin(redis_client, uid)):
                    await _tg_send(token, chat_id, "❌ אין הרשאת אדמין. לחץ Admin Login והכנס סיסמה.")
                    return

                if text == "admin:status":
                    rc = False
                    try:
                        rc = bool(redis_client)
                    except Exception:
                        rc = False
                    pwd_set = bool((os.getenv("ADMIN_PASSWORD") or "").strip())
                    msg = (
                        "STATUS\n"
                        f"online=true\n"
                        f"redis_configured={rc}\n"
                        f"admin_password_set={pwd_set}\n"
                        f"uid={uid}\n"
                        f"chat_id={chat_id}"
                    )
                    await _tg_send(token, chat_id, msg)
                    return
                if text == "admin:chatid":
                    await _tg_send(token, chat_id, f"chat_id={chat_id}\nuser_id={uid}")
                    return

                if text == "admin:logout":
                    try:
                        await redis_client.delete(f"admin:session:{uid}")
                    except Exception:
                        pass
                    await _tg_send(token, chat_id, "🚪 התנתקת. לחץ Admin Login כדי להתחבר שוב.")
                    return

                await _tg_send(token, chat_id, "בחר פעולה:", _admin_menu())
                return

            # default: ignore quietly
        except Exception as e:
            logging.getLogger("app").exception("tg handle failed: %s", str(e)[:200])

    background.add_task(_handle)
    return {"ok": True}
@app.on_event("startup")
async def startup():
    # Backward/forward compatible toggles:
    # - DISABLE_TELEGRAM=1 disables
    # - ENABLE_TELEGRAM_BOT=0 disables
    disable_telegram = str(os.getenv("DISABLE_TELEGRAM", "")).strip().lower() in {"1", "true", "yes", "on"}
    enable_bot_raw = os.getenv("ENABLE_TELEGRAM_BOT")
    enable_bot = True if enable_bot_raw is None else str(enable_bot_raw).strip().lower() not in {"0", "false", "no", "off", ""}

    if disable_telegram or (not enable_bot):
        log.info("telegram disabled (DISABLE_TELEGRAM=1 or ENABLE_TELEGRAM_BOT=0)")
        return

    # Import only when enabled so BOT_TOKEN isn't required when disabled
    from app.bot.investor_wallet_bot import ensure_handlers
    ensure_handlers()
    log.info("telegram bot initialized")


