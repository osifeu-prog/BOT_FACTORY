from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# --- ensure imports (best-effort) ---
needed = [
    "import os",
    "import json",
    "import logging",
    "import httpx",
    "from fastapi import Request, BackgroundTasks",
]
for imp in needed:
    if imp not in t:
        # Try insert after first import-ish line
        t = re.sub(
            r"(?m)\A((?:from\s+\S+\s+import\s+.*|import\s+\S+.*)\n)",
            lambda m: m.group(1) + imp + "\n",
            t,
            count=1,
        )
        if imp not in t:
            # fallback: prepend
            t = imp + "\n" + t

# --- helpers (added once) ---
if "def _extract_message(update: dict) -> dict:" not in t:
    helpers = r'''
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
'''
    t = t + "\n" + helpers + "\n"

# --- replace webhook block ---
pattern = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pattern, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block to replace")

replacement = r'''@app.post("/webhook/telegram")
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
    if not (token and chat_id):
        return {"ok": True}

    async def _handle():
        try:
            uid = int(user_id or 0)

            # pending admin password flow (after clicking Admin Login)
            if uid and await _has_pending_login(redis, uid) and text and not text.startswith("admin:") and not text.startswith("public:"):
                await _clear_pending_login(redis, uid)

                need = (os.getenv("ADMIN_PASSWORD") or "").strip()
                if not need:
                    await _tg_send(token, chat_id, "❌ ADMIN_PASSWORD לא מוגדר בשרת.")
                    return

                if text.strip() == need:
                    ok = await _grant_admin(redis, uid)
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
                if uid and await _is_admin(redis, uid):
                    await _tg_send(token, chat_id, "✅ כבר מחובר כאדמין.\nבחר פעולה:", _admin_menu())
                    return

                await _set_pending_login(redis, uid)
                await _tg_send(
                    token,
                    chat_id,
                    "הכנס סיסמת אדמין (Reply להודעה הזו):",
                    {"force_reply": True, "selective": True},
                )
                return

            # admin actions (only if logged in)
            if text.startswith("admin:"):
                if not (uid and await _is_admin(redis, uid)):
                    await _tg_send(token, chat_id, "❌ אין הרשאת אדמין. לחץ Admin Login והכנס סיסמה.")
                    return

                if text == "admin:status":
                    await _tg_send(token, chat_id, "📊 סטטוס: ONLINE ✅\n/health תקין.")
                    return

                if text == "admin:chatid":
                    await _tg_send(token, chat_id, f"chat_id={chat_id}\nuser_id={uid}")
                    return

                if text == "admin:logout":
                    try:
                        await redis.delete(f"admin:session:{uid}")
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
'''
t2 = t[:m.start()] + replacement + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: /start buttons + admin login flow (button -> password -> admin panel)")