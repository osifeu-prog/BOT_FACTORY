from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Remove the broken tail that starts with a lonely quote line and ends right before rc_ok assignment.
# We anchor on exactly what we saw in your file: a line that is only a quote (optional spaces) and later "rc_ok = await _redis_healthcheck"
pat = r'(?ms)^\s*"\s*$.*?^(?=\s*rc_ok\s*=\s*await\s*_redis_healthcheck\()'
m = re.search(pat, t)
if not m:
    raise SystemExit("ERROR: could not find broken admin:status tail pattern")

t2 = t[:m.start()] + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: removed broken unterminated-string tail before rc_ok block")