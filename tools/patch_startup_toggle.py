from pathlib import Path
import re

p = Path("app/main.py")
s = p.read_text(encoding="utf-8")

# Ensure `import os`
if not re.search(r'^\s*import\s+os\s*$', s, flags=re.M):
    m = re.search(r'^(from __future__.*\n)?(import .*?\n|from .*? import .*?\n)+', s, flags=re.M)
    if m:
        insert_at = m.end()
        s = s[:insert_at] + "import os\n" + s[insert_at:]
    else:
        s = "import os\n" + s

# Replace startup() block (best-effort, assumes def _extract_message follows)
pattern = r'@app\.on_event\("startup"\)\s*\nasync def startup\(\):\s*\n(?:(?:\s+.*\n)+?)\n(?=def _extract_message|\Z)'
m = re.search(pattern, s, flags=re.M)
if not m:
    raise SystemExit("Could not find startup() block in app/main.py")

startup_block = '''@app.on_event("startup")
async def startup():
    # Backward/forward compatible toggles:
    # - DISABLE_TELEGRAM=1 disables
    # - ENABLE_TELEGRAM_BOT=0 disables
    disable_telegram = str(os.getenv("DISABLE_TELEGRAM", "")).strip().lower() in {"1", "true", "yes", "on"}
    enable_bot_raw = os.getenv("ENABLE_TELEGRAM_BOT")
    enable_bot = True if enable_bot_raw is None else str(enable_bot_raw).strip().lower() not in {"0", "false", "no", "off", ""}

    if disable_telegram or (not enable_bot):
        log.info("telegram disabled (DISABLE_TELEGRAM=1 or ENABLE_TELEGRAM_BOT=0)")
        return

    # Import only when enabled so BOT_TOKEN isn't required when disabled
    from app.bot.investor_wallet_bot import ensure_handlers
    ensure_handlers()
    log.info("telegram bot initialized")
'''

s = re.sub(pattern, startup_block + "\n\n", s, flags=re.M)
p.write_text(s, encoding="utf-8")
print("✅ Patched app/main.py")
# patch helper: api-only toggle (generated)
