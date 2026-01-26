from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Replace the entire admin:status branch body with a minimal safe version
pat = r'(?ms)(if\s+text\s*==\s*"admin:status"\s*:\s*\n)(.*?)(\n\s*(elif|else|return)\b)'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: cannot find admin:status block")

safe_body = (
    "                msg = ("
    "\"STATUS\\n\""
    "f\"online=true\\n\""
    "f\"uid={uid}\\n\""
    "f\"chat_id={chat_id}\""
    ")\n"
    "                await _tg_send(token, chat_id, msg)\n"
)

t2 = t[:m.start(2)] + safe_body + t[m.end(2):]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: admin:status replaced with safe minimal block")