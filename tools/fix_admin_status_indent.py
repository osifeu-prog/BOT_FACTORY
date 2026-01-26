from __future__ import annotations
from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Find the exact line: if text == "admin:status":
m = re.search(r'(?m)^(?P<indent>[ \t]*)if text == "admin:status":\s*$', t)
if not m:
    raise SystemExit('ERROR: cannot find: if text == "admin:status":')

indent = m.group("indent")
inner = indent + (" " * 4)

start = m.start()

# Find the end of this if-block:
# next line that is either another "if text ..." at same indent, or "return" at same indent, or end of file.
tail = t[m.end():]
m2 = re.search(r'(?m)^(?:' + re.escape(indent) + r'(?:if text\b|return\b)|^\S)', tail)
end = m.end() + (m2.start() if m2 else len(tail))

replacement = (
    indent + 'if text == "admin:status":\n'
    + inner + 'rc = False\n'
    + inner + 'try:\n'
    + inner + '    rc = bool(redis_client)\n'
    + inner + 'except Exception:\n'
    + inner + '    rc = False\n'
    + inner + 'pwd_set = bool((os.getenv("ADMIN_PASSWORD") or "").strip())\n'
    + inner + 'msg = (\n'
    + inner + '    "STATUS\\n"\n'
    + inner + '    f"online=true\\n"\n'
    + inner + '    f"redis_configured={rc}\\n"\n'
    + inner + '    f"admin_password_set={pwd_set}\\n"\n'
    + inner + '    f"uid={uid}\\n"\n'
    + inner + '    f"chat_id={chat_id}"\n'
    + inner + ')\n'
    + inner + 'await _tg_send(token, chat_id, msg)\n'
    + inner + 'return\n'
)

t2 = t[:start] + replacement + t[end:]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: rewrote admin:status block with correct indentation")