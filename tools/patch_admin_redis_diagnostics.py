from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Ensure helper exists: _get_redis_client(request)
if "def _get_redis_client(request):" not in t:
    helpers = r"""
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
"""
    t = t + "\n" + helpers + "\n"

# Find webhook block
pat = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block")

block = m.group(0)

# Ensure we set redis_client via helper near the top of webhook
if "redis_client = _get_redis_client(request)" not in block:
    # Insert after token assignment (or near token block)
    token_line = r'(?m)^\s*token\s*=\s*os\.getenv\("TELEGRAM_TOKEN"\)\s*or\s*os\.getenv\("BOT_TOKEN"\)\s*$'
    ins = "\n    redis_client = _get_redis_client(request)\n"
    if re.search(token_line, block):
        block = re.sub(token_line, lambda mm: mm.group(0) + ins, block, count=1)
    else:
        # fallback: after log.info line
        anchor = r'(?m)^\s*log\.info\(.*\)\s*$'
        if re.search(anchor, block):
            block = re.sub(anchor, lambda mm: mm.group(0) + ins, block, count=1)
        else:
            # last resort: right after function signature line
            block = re.sub(r'(?m)^(async def telegram_webhook\(.*?\):\s*)$',
                           lambda mm: mm.group(0) + "\n    redis_client = _get_redis_client(request)\n",
                           block, count=1)

# Replace any remaining redis usage to redis_client in call sites (idempotent)
repls = [
    ("_has_pending_login(redis, ", "_has_pending_login(redis_client, "),
    ("_set_pending_login(redis, ", "_set_pending_login(redis_client, "),
    ("_clear_pending_login(redis, ", "_clear_pending_login(redis_client, "),
    ("_is_admin(redis, ", "_is_admin(redis_client, "),
    ("_grant_admin(redis, ", "_grant_admin(redis_client, "),
    ("await redis.delete(", "await redis_client.delete("),
]
for a, b in repls:
    block = block.replace(a, b)

# Improve admin:login flow so it fails loudly if redis is missing
# Insert check inside admin:login handler (best-effort string replace)
needle = 'if text == "admin:login":'
if needle in block and "Redis not connected" not in block:
    block = block.replace(
        needle,
        needle + r'''
                # Require Redis for login/session; otherwise user will be stuck
                if not await _redis_healthcheck(redis_client):
                    await _tg_send(token, chat_id, "⚠️ Redis לא מחובר/לא נגיש כרגע. לא ניתן לבצע Admin Login.\nבדוק ש-REDIS_URL קיים ושאתחול Redis הצליח בלוגים.")
                    return
'''
    )

# Add richer admin:status output (includes redis/session/pending)
# Best-effort: find admin:status handler and replace its message
status_old = 'if text == "admin:status":'
if status_old in block and "redis_connected" not in block:
    # crude replace of the body line that sends status
    block = re.sub(
        r'(?ms)if text == "admin:status":\s*\n\s*await _tg_send\(token, chat_id, .*?\)\s*\n\s*return',
        r'''if text == "admin:status":
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
                    await _tg_send(
                        token,
                        chat_id,
                        f"✅ STATUS\nonline=true\nredis_connected={rc_ok}\nadmin_password_set={pwd_set}\npending_login={pending}\nsession_active={session}\nuid={uid}\nchat_id={chat_id}",
                    )
                    return''',
        block,
        count=1
    )

t2 = t[:m.start()] + block + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: webhook now uses robust redis_client + diagnostics + loud failure if Redis missing")