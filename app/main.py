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
"
                        f"online=true
"
                        f"redis_connected={rc_ok}
"
                        f"admin_password_set={pwd_set}
"
                        f"pending_login={pending}
"
                        f"session_active={session}
"
                        f"uid={uid}
"
                        f"chat_id={chat_id}"
                    )
                rc_ok = await _redis_healthcheck(redis_client)
                    pending = False
                    session = False
                    try:
                        pending = bool(await redis_client.get(f"admin:pending:{uid}")) if rc_ok else False
                        session = bool(await redis_client.get(f"admin:session:{uid}")) if rc_ok else False
                    except Exception:
                        pending = False
                        session = False
                    pwd_set = bool((os.getenv("ADMIN_PASSWORD") or "").strip())
                    msg = (
                        "STATUS
"
                        f"online=true
"
                        f"redis_connected={rc_ok}
"
                        f"admin_password_set={pwd_set}
"
                        f"pending_login={pending}
"
                        f"session_active={session}
"
                        f"uid={uid}
"
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
    if DISABLE_TELEGRAM:
        log.info("telegram disabled (DISABLE_TELEGRAM=1)")
        return

    # Import only when enabled so BOT_TOKEN isn't required when disabled
    from app.bot.investor_wallet_bot import ensure_handlers
    ensure_handlers()
    log.info("telegram bot initialized")


def _extract_message(update: dict) -> dict:
    msg = update.get("message") or update.get("edited_message") or {}
    cbq = update.get("callback_query") or {}
    if cbq and cbq.get("message"):
        # callback query carries message context; treat as message-like
        msg = cbq.get("message") or msg
        msg["_callback_data"] = (cbq.get("data") or "").strip()
        msg["_callback_from_id"] = ((cbq.get("from") or {}).get("id"))
    return msg or {}

def _chat_id(msg: dict):
    return (msg.get("chat") or {}).get("id")

def _from_id(msg: dict):
    return (msg.get("from") or {}).get("id")

def _text_or_callback(msg: dict) -> str:
    if msg.get("_callback_data"):
        return msg.get("_callback_data")
    return (msg.get("text") or "").strip()

async def _tg_send(token: str, chat_id: int, text: str, reply_markup: dict | None = None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=12) as client:
        await client.post(url, json=payload)

def _start_menu():
    return {
        "inline_keyboard": [
            [{"text": "📌 הצג chat_id", "callback_data": "public:chatid"}],
            [{"text": "🔐 Admin Login", "callback_data": "admin:login"}],
        ]
    }

def _admin_menu():
    return {
        "inline_keyboard": [
            [{"text": "📊 סטטוס", "callback_data": "admin:status"}],
            [{"text": "📌 chat_id", "callback_data": "admin:chatid"}],
            [{"text": "🚪 Logout", "callback_data": "admin:logout"}],
        ]
    }

def _admin_session_ttl() -> int:
    try:
        return int(os.getenv("ADMIN_SESSION_TTL_SECONDS") or "604800")  # 7d
    except Exception:
        return 604800

def _admin_pending_ttl() -> int:
    try:
        return int(os.getenv("ADMIN_LOGIN_PENDING_TTL_SECONDS") or "300")  # 5m
    except Exception:
        return 300

async def _is_admin(db_redis, user_id: int) -> bool:
    try:
        admin_id = int(os.getenv("ADMIN_USER_ID") or "0")
    except Exception:
        admin_id = 0
    if admin_id and user_id == admin_id:
        return True
    if not db_redis or not user_id:
        return False
    try:
        v = await db_redis.get(f"admin:session:{user_id}")
        return bool(v)
    except Exception:
        return False

async def _grant_admin(db_redis, user_id: int) -> bool:
    if not db_redis or not user_id:
        return False
    try:
        await db_redis.set(f"admin:session:{user_id}", "1", ex=_admin_session_ttl())
        return True
    except Exception:
        return False

async def _set_pending_login(db_redis, user_id: int) -> bool:
    if not db_redis or not user_id:
        return False
    try:
        await db_redis.set(f"admin:pending:{user_id}", "1", ex=_admin_pending_ttl())
        return True
    except Exception:
        return False

async def _has_pending_login(db_redis, user_id: int) -> bool:
    if not db_redis or not user_id:
        return False
    try:
        v = await db_redis.get(f"admin:pending:{user_id}")
        return bool(v)
    except Exception:
        return False

async def _clear_pending_login(db_redis, user_id: int):
    if not db_redis or not user_id:
        return
    try:
        await db_redis.delete(f"admin:pending:{user_id}")
    except Exception:
        pass



def _get_redis_client(request):
    # Try multiple places (app.state + module-level fallbacks)
    try:
        st = getattr(getattr(request, "app", None), "state", None)
    except Exception:
        st = None

    for name in ("redis", "redis_client", "redis_conn", "redis_async", "redis_pool"):
        try:
            if st is not None and getattr(st, name, None) is not None:
                return getattr(st, name)
        except Exception:
            pass

    # module fallbacks (best-effort)
    for modname in ("app.redis", "app.db", "app.main"):
        try:
            mod = __import__(modname, fromlist=["*"])
            for name in ("redis", "redis_client", "client", "r"):
                if getattr(mod, name, None) is not None:
                    return getattr(mod, name)
        except Exception:
            pass

    return None

async def _redis_healthcheck(rc) -> bool:
    if rc is None:
        return False
    try:
        # minimal set/get roundtrip
        k = "diag:redis:ping"
        await rc.set(k, "1", ex=15)
        v = await rc.get(k)
        return (v is not None)
    except Exception:
        return False

