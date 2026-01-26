from __future__ import annotations

from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# match the admin:status branch (if OR elif)
pat = r'(?ms)^(?P<indent>\s*)(?P<kw>elif|if)\s+text\s*==\s*["\']admin:status["\']\s*:\s*\n(?P<body>.*?)(?=^(?P=indent)(?:elif|else)\b|^\S|\Z)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: cannot find admin:status branch (if/elif text == 'admin:status')")

indent = m.group("indent")
body_indent = indent + " " * 4

safe = []
safe.append(f"{body_indent}pwd_set = bool((os.getenv('ADMIN_PASSWORD') or '').strip())")
safe.append(f"{body_indent}rc = False")
safe.append(f"{body_indent}try:")
safe.append(f"{body_indent}    rc = bool(redis_client)")
safe.append(f"{body_indent}except Exception:")
safe.append(f"{body_indent}    rc = False")
safe.append(f"{body_indent}msg = ('STATUS\\n'"
           f\"online=true\\n\"
           f\"redis_configured={rc}\\n\"
           f\"admin_password_set={pwd_set}\\n\"
           f\"uid={uid}\\n\"
           f\"chat_id={chat_id}\")")
safe.append(f"{body_indent}await _tg_send(token, chat_id, msg)")
safe.append(f"{body_indent}return")

safe_body = "\n".join(safe) + "\n"

t2 = t[:m.start("body")] + safe_body + t[m.end("body"):]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")

print("OK: replaced admin:status branch with minimal safe block")