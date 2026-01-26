from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Match the admin:status branch whether it's "if" or "elif"
pat = r'(?ms)^(?P<indent>\s*)(?:elif|if)\s+text\s*==\s*["\']admin:status["\']\s*:\s*\n(?P<body>.*?)(?=^\s*(?:elif|else|#|return\b|try\b|except\b|async def\b|def\b|@|\Z))'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: cannot find admin:status branch (if/elif text == 'admin:status')")

indent = m.group("indent")
body_indent = indent + " " * 4

safe = []
safe.append(f"{body_indent}msg = 'STATUS\\n'")
safe.append(f"{body_indent}msg += 'online=true\\n'")
safe.append(f"{body_indent}msg += f'uid={uid}\\n'")
safe.append(f"{body_indent}msg += f'chat_id={chat_id}\\n'")
safe.append(f"{body_indent}await _tg_send(token, chat_id, msg)")
safe.append(f"{body_indent}return")
safe_body = "\n".join(safe) + "\n"

t2 = t[:m.start("body")] + safe_body + t[m.end("body"):]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: replaced admin:status branch with minimal safe block")