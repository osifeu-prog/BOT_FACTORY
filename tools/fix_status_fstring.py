from __future__ import annotations
from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Replace the broken multi-line f-string that starts with f" STATUS ... (unterminated)
# Strategy: find the admin:status block and replace the await _tg_send(...) message with a safe \n-joined f-string.
pat = r'(?ms)(if text == "admin:status":\s*\n)(.*?)(\n\s*return)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find admin:status block")

block_body = m.group(2)

# Replace any await _tg_send(...) inside this block with safe one-liner
# We keep it simple & robust.
safe = r'''                rc_ok = await _redis_healthcheck(redis_client)
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
                        "STATUS\n"
                        f"online=true\n"
                        f"redis_connected={rc_ok}\n"
                        f"admin_password_set={pwd_set}\n"
                        f"pending_login={pending}\n"
                        f"session_active={session}\n"
                        f"uid={uid}\n"
                        f"chat_id={chat_id}"
                    )
                    await _tg_send(token, chat_id, msg)'''

# If there is an await _tg_send in body, replace whole body with safe block
block_body2 = re.sub(r'(?ms)^\s*await _tg_send\(.*?\)\s*$', safe, block_body)
# If substitution did nothing, just overwrite the body entirely (best-effort)
if block_body2 == block_body:
    block_body2 = safe

t2 = t[:m.start(2)] + block_body2 + t[m.end(2):]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: fixed admin:status message (no multi-line f-string)")