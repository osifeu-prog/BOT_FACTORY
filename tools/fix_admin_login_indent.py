from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")

# Work only inside the telegram webhook block to avoid collateral edits
pat = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block")

block = m.group(0)

# 1) Remove the duplicated/over-indented Redis guard (the one that caused IndentationError)
#    It looks like:
#        <lots of spaces>if not redis_client:
#            await _tg_send(... 'ADMIN login requires Redis ...')
#            return
block2 = re.sub(
    r'(?ms)^[ \t]{20,}if not redis_client:\s*\n[ \t]*await _tg_send\([^\n]*ADMIN login requires Redis[^\n]*\)\s*\n[ \t]*return\s*\n',
    "",
    block
)

# 2) Fix the _set_pending_login line that fell out of indentation
#    Replace any top-level "await _set_pending_login(" with a properly indented one.
block2 = re.sub(
    r'(?m)^(await _set_pending_login\()',
    r'                \1',
    block2
)

# 3) ALSO ensure that _set_pending_login is called with redis_client (not redis)
block2 = block2.replace("await _set_pending_login(redis, ", "await _set_pending_login(redis_client, ")

# Put back
t2 = t[:m.start()] + block2 + t[m.end():]
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: fixed admin:login indentation + removed duplicate redis_client guard")