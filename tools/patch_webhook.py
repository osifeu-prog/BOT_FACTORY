from pathlib import Path
import re

p = Path("app/main.py")
t = p.read_text(encoding="utf-8", errors="replace")

# Ensure required imports exist (idempotent-ish)
need = [
    "import os",
    "import json",
    "import logging",
    "import httpx",
    "from fastapi import Request, BackgroundTasks",
]
for imp in need:
    if imp not in t:
        # naive: insert after existing imports section
        t = re.sub(r'(?m)^(from fastapi import .*|import .*|from .* import .*)\n(?!from fastapi import|import |from )',
                   lambda m: m.group(0) + imp + "\n",
                   t, count=1)

# Replace webhook block
pattern = r'(?ms)^@app\.post\("/webhook/telegram"\)\s*\nasync def telegram_webhook\(.*?\):\s*\n.*?(?=^\S|\Z)'
m = re.search(pattern, t)
if not m:
    raise SystemExit("ERROR: could not find telegram_webhook block to replace")

replacement = r'''@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background: BackgroundTasks):
    raw = await request.body()
    try:
        upd = json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        upd = {}

    msg = (upd.get("message") or upd.get("edited_message") or {})
    text = (msg.get("text") or "").strip()
    chat = (msg.get("chat") or {})
    chat_id = chat.get("id")

    logging.getLogger("app").info("tg webhook: update_id=%s text=%s chat_id=%s",
                                  upd.get("update_id"), text[:50], chat_id)

    token = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")  # support both env names
    if token and chat_id and text:
        async def _send():
            try:
                if text.startswith("/start"):
                    reply = "✅ BOT_FACTORY online. (/start OK)"
                elif text.startswith("/chatid"):
                    reply = f"chat_id = {chat_id}"
                else:
                    reply = f"echo: {text}"

                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": reply}
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(url, json=payload)
            except Exception as e:
                logging.getLogger("app").exception("sendMessage failed: %s", str(e)[:200])

        background.add_task(_send)

    return {"ok": True}
'''
t2 = t[:m.start()] + replacement + t[m.end():]
t2 = t2.replace("\r\n", "\n").replace("\r", "\n")
p.write_text(t2, encoding="utf-8", newline="\n")
print("OK: webhook now replies to /start and /chatid (async)")