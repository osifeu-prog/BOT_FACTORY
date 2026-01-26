from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# ---- 0) Ensure helper: redis healthcheck + lazy redis (only if missing) ----
if "async def _redis_healthcheck(" not in t:
    helper = r'''
async def _redis_healthcheck(redis_client) -> bool:
    if not redis_client:
        return False
    try:
        # most redis clients support ping()
        r = redis_client.ping()
        if hasattr(r, "__await__"):
            await r
        return True
    except Exception:
        return False

def _lazy_redis_from_env():
    try:
        import os
        url = (os.getenv("REDIS_URL") or "").strip()
        if not url:
            return None
        try:
            import redis.asyncio as redis_async
            return redis_async.from_url(url, decode_responses=True)
        except Exception:
            # fallback older import style
            import redis as redis_sync
            return redis_sync.Redis.from_url(url, decode_responses=True)
    except Exception:
        return None
'''
    t = t + "\n" + helper + "\n"

# ---- 1) Locate webhook block ----
pat = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block")

block = m.group(0)

# ---- 2) Ensure redis_client init inside telegram_webhook (robust) ----
if "redis_client =" not in block:
    ins = '''
    # redis may live on request.app.state; keep webhook resilient if missing
    redis_client = None
    try:
        st = getattr(getattr(request, "app", None), "state", None)
        redis_client = getattr(st, "redis", None) or getattr(st, "redis_client", None)
    except Exception:
        redis_client = None
    if redis_client is None:
        redis_client = _lazy_redis_from_env()
'''
    # inject after token assignment if present, else after msg parsing section
    token_line = r'(?m)^\s*token\s*=\s*os\.getenv\("TELEGRAM_TOKEN"\)\s*or\s*os\.getenv\("BOT_TOKEN"\)\s*$'
    if re.search(token_line, block):
        block = re.sub(token_line, lambda mm: mm.group(0) + ins, block, count=1)
    else:
        # fallback: add near top (after msg/text computed)
        anchor = r'(?m)^\s*text\s*=\s*_text_or_callback\(msg\)\s*$'
        if re.search(anchor, block):
            block = re.sub(anchor, lambda mm: mm.group(0) + "\n" + ins, block, count=1)
        else:
            block = re.sub(r'(?m)^(async def telegram_webhook\(.*?\):\s*)$',
                           lambda mm: mm.group(0) + ins, block, count=1)

# ---- 3) Normalize redis variable usage inside webhook handler ----
block = block.replace("_has_pending_login(redis, ", "_has_pending_login(redis_client, ")
block = block.replace("_set_pending_login(redis, ", "_set_pending_login(redis_client, ")
block = block.replace("_clear_pending_login(redis, ", "_clear_pending_login(redis_client, ")
block = block.replace("_is_admin(redis, ", "_is_admin(redis_client, ")
block = block.replace("_grant_admin(redis, ", "_grant_admin(redis_client, ")
block = block.replace("await redis.delete(", "await redis_client.delete(")

# ---- 4) Add chat_type/is_private vars (for ACK policy) ----
if "chat_type =" not in block:
    block = re.sub(
        r'(?m)^\s*text\s*=\s*_text_or_callback\(msg\)\s*$',
        lambda mm: mm.group(0) + "\n    chat_type = ((msg.get('chat') or {}).get('type') or '').strip()\n    is_private = (chat_type == 'private')\n",
        block,
        count=1,
    )

# ---- 5) Admin login button: if no redis -> explain (instead of silent fail) ----
# Add check right before calling _set_pending_login
block = re.sub(
    r'(?ms)(if text == "admin:login":\s*\n)(.*?)(await _set_pending_login\(redis_client, uid\))',
    lambda mm: mm.group(1) + mm.group(2) +
               "                if not redis_client:\n"
               "                    await _tg_send(token, chat_id, 'ADMIN login requires Redis, but Redis is not connected. Check REDIS_URL / Railway Redis service.')\n"
               "                    return\n\n" +
               mm.group(3),
    block,
    count=1
)

# ---- 6) Pending password flow: if redis missing -> explain; also always ACK wrong flow ----
# Insert a guard at the start of pending flow condition handling:
if "pending admin password flow" in block and "ADMIN login requires Redis" not in block:
    pass  # already handled above

# ---- 7) Default handler: in private chat always ACK+ECHO+placeholder (instead of ignore quietly) ----
# Replace the "default: ignore quietly" comment section if exists; else append before _handle ends.
if "default: ignore quietly" in block:
    block = block.replace(
        "# default: ignore quietly",
        "# default: ACK in private chats for debugging\n"
        "            if is_private:\n"
        "                src = 'callback' if msg.get('_callback_data') else 'text'\n"
        "                got = (text or '')\n"
        "                note = (\n"
        "                    'ACK: received your message.\\n'\n"
        "                    'Function will be added soon.\\n'\n"
        "                    f'source={src}\\n'\n"
        "                    f'text={got}\\n'\n"
        "                    f'chat_id={chat_id}\\n'\n"
        "                    f'user_id={uid}'\n"
        "                )\n"
        "                await _tg_send(token, chat_id, note)\n"
        "                return\n"
        "            # in groups: stay silent by default\n"
    )
else:
    # best-effort: before exception handler end of _handle, add a private ACK fallback
    block = re.sub(
        r'(?ms)(\s*# default:.*?\n)?(\s*except Exception as e:\s*\n\s*logging\.getLogger\("app"\)\.exception)',
        lambda mm: (
            "            # default fallback: ACK in private chats\n"
            "            if is_private:\n"
            "                src = 'callback' if msg.get('_callback_data') else 'text'\n"
            "                got = (text or '')\n"
            "                note = (\n"
            "                    'ACK: received your message.\\n'\n"
            "                    'Function will be added soon.\\n'\n"
            "                    f'source={src}\\n'\n"
            "                    f'text={got}\\n'\n"
            "                    f'chat_id={chat_id}\\n'\n"
            "                    f'user_id={uid}'\n"
            "                )\n"
            "                await _tg_send(token, chat_id, note)\n"
            "                return\n\n"
        ) + mm.group(2),
        block,
        count=1
    )

# ---- 8) Put webhook back ----
t2 = t[:m.start()] + block + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: patched admin login Redis guard + private ACK/ECHO placeholder in webhook")