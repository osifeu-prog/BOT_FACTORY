from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Replace the whole admin:status branch with a minimal safe version (no multiline f-strings)
pat = r'(?ms)(^\s*if\s+text\s*==\s*"admin:status"\s*:\s*\n)(.*?)(^\s*(elif|else)\b)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: cannot find admin:status block")

head = m.group(1)
tail = m.group(3)

# Detect indent level from the 'if' line and add +4 spaces for body
if_indent = re.match(r'^(\s*)if', head).group(1)
body_indent = if_indent + " " * 4

safe = []
safe.append(f'{body_indent}msg = "STATUS\\n"')
safe.append(f'{body_indent}msg += f"online=true\\n"')
safe.append(f'{body_indent}msg += f"uid={uid}\\n"')
safe.append(f'{body_indent}msg += f"chat_id={chat_id}\\n"')
safe.append(f'{body_indent}await _tg_send(token, chat_id, msg)')
safe_body = "\n".join(safe) + "\n"

t2 = t[:m.start(2)] + safe_body + t[m.end(2):]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: admin:status replaced with minimal safe block")