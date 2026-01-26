from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Find webhook block (from decorator to next top-level decorator/def or EOF)
pat = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block")

block = m.group(0)

# 1) Ensure we define redis_client safely inside telegram_webhook
if "redis_client =" not in block:
    # Insert after token line if exists, else after token assignment fallback
    ins = '''
    # redis may live on request.app.state; keep webhook resilient if missing
    redis_client = None
    try:
        redis_client = getattr(getattr(request, "app", None), "state", None)
        redis_client = getattr(redis_client, "redis", None)
    except Exception:
        redis_client = None
'''
    # place right after: token = ...
    token_line = r'(?m)^\s*token\s*=\s*os\.getenv\("TELEGRAM_TOKEN"\)\s*or\s*os\.getenv\("BOT_TOKEN"\)\s*$'
    if re.search(token_line, block):
        block = re.sub(token_line, lambda mm: mm.group(0) + ins, block, count=1)
    else:
        # fallback: put near the beginning after parsing update/msg/chat_id
        anchor = r'(?m)^\s*token\s*='
        if re.search(anchor, block):
            block = re.sub(anchor, lambda mm: ins + mm.group(0), block, count=1)
        else:
            # ultimate fallback: add after function signature line
            block = re.sub(r'(?m)^(async def telegram_webhook\(.*?\):\s*)$',
                           lambda mm: mm.group(0) + ins, block, count=1)

# 2) Replace ONLY inside webhook handler usage: redis -> redis_client
# handle common call sites
block = block.replace("_has_pending_login(redis, ", "_has_pending_login(redis_client, ")
block = block.replace("_set_pending_login(redis, ", "_set_pending_login(redis_client, ")
block = block.replace("_clear_pending_login(redis, ", "_clear_pending_login(redis_client, ")
block = block.replace("_is_admin(redis, ", "_is_admin(redis_client, ")
block = block.replace("_grant_admin(redis, ", "_grant_admin(redis_client, ")

# delete/logout calls
block = block.replace("await redis.delete(", "await redis_client.delete(")

# also protect any remaining standalone " redis " in those contexts (safe-ish)
# (but do not touch function params like db_redis)
block = re.sub(r'(?m)\bredis\b', lambda mm: "redis_client" if mm.group(0) == "redis" else mm.group(0), block)

# Put block back
t2 = t[:m.start()] + block + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: fixed webhook redis reference -> redis_client (request.app.state.redis fallback)")