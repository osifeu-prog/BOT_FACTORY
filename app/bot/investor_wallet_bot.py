from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler

from app.core.config import settings
from app.bot.handlers import start_cmd, menu_cmd, history_cmd, referrals_cmd

log = logging.getLogger("bot")

def build_application() -> Application:
    app = Application.builder().token(settings.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("referrals", referrals_cmd))
    return app

async def process_webhook_update(tg_app: Application, payload: dict) -> None:
    update = Update.de_json(payload, tg_app.bot)
    await tg_app.process_update(update)