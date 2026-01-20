from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("bot_factory")


def env_str(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def env_int(name: str, default: int) -> int:
    v = env_str(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        logger.warning("Invalid int for %s=%r, using default=%d", name, v, default)
        return default


app = FastAPI(title="BOT_FACTORY", version="1.0.0")

BOT_TOKEN = env_str("BOT_TOKEN")
WEBHOOK_URL = env_str("WEBHOOK_URL")  # https://tease-production.up.railway.app
WEBHOOK_PATH = env_str("WEBHOOK_PATH", "/webhook/telegram")  # match your existing webhook
WEBHOOK_SECRET = env_str("WEBHOOK_SECRET")  # optional custom secret (query/header)
BOT_USERNAME = env_str("BOT_USERNAME")  # without @ (optional)

tg_app: Optional[Application] = None
tg_started = False


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"


@app.get("/ready", response_class=PlainTextResponse)
async def ready() -> str:
    return "ok"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(" BOT_FACTORY online. Use commands in private chat.")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text("pong")


def _is_direct_message(update: Update) -> bool:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat:
        return False

    if chat.type == "private":
        return True

    # group/supergroup: allow only reply-to-bot or mention
    if msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.is_bot:
        return True

    if BOT_USERNAME:
        text = (msg.text or msg.caption or "")
        if f"@{BOT_USERNAME.lstrip('@')}" in text:
            return True

    return False


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> JSONResponse:
    if tg_app is None:
        raise HTTPException(status_code=503, detail="Telegram app not initialized")

    # optional secret
    if WEBHOOK_SECRET:
        q_secret = request.query_params.get("secret")
        h_secret = request.headers.get("X-Webhook-Secret")
        if (q_secret != WEBHOOK_SECRET) and (h_secret != WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    try:
        update = Update.de_json(payload, tg_app.bot)  # type: ignore[arg-type]
    except Exception as e:
        logger.exception("Failed to parse update: %s", e)
        raise HTTPException(status_code=400, detail="Bad update payload")

    if not _is_direct_message(update):
        return JSONResponse({"ok": True, "ignored": True})

    try:
        await tg_app.process_update(update)
    except Exception as e:
        logger.exception("process_update failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})

    return JSONResponse({"ok": True})


async def _init_telegram() -> None:
    global tg_app, tg_started

    if tg_started:
        return
    tg_started = True

    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN not set -> API-only mode")
        tg_app = None
        return

    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("ping", cmd_ping))

    await tg_app.initialize()
    await tg_app.start()

    if WEBHOOK_URL:
        webhook_full = WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
        if WEBHOOK_SECRET:
            webhook_full += f"?secret={WEBHOOK_SECRET}"

        try:
            await tg_app.bot.set_webhook(url=webhook_full, drop_pending_updates=True)
            logger.info("Webhook set: %s", webhook_full)
        except Exception as e:
            logger.exception("Failed setting webhook: %s", e)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(_init_telegram())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global tg_app
    if tg_app is None:
        return
    try:
        await tg_app.stop()
        await tg_app.shutdown()
    except Exception:
        logger.exception("Error during Telegram shutdown")


if __name__ == "__main__":
    import uvicorn

    port = env_int("PORT", 8080)
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())