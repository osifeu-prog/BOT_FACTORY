from pathlib import Path

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

start = t.find("rc_ok = await _redis_healthcheck(redis_client)")
end = t.find('if text == "admin:chatid":')

if start == -1:
    raise SystemExit("ERROR: start marker not found: rc_ok = await _redis_healthcheck(redis_client)")
if end == -1:
    raise SystemExit('ERROR: end marker not found: if text == "admin:chatid":')
if end <= start:
    raise SystemExit("ERROR: end marker occurs before start marker")

t2 = t[:start] + t[end:]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")

print("OK: removed broken admin:status tail (rc_ok.. before admin:chatid)")