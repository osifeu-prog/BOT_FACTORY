from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logger = logging.getLogger(__name__)

# מצופה שמוגדרים בסביבה / settings שלך
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is empty; Telegram webhook processing will fail until set.")

_tg_app: Optional[Application] = None
_handlers_ready: bool = False


# ----------------------------
# Handlers (מינימום בטוח)
# ----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "ברוך הבא ל-SLH Investor Gateway.\n\n"
        "פקודות זמינות:\n"
        "/whoami\n"
        "/balance\n"
        "/history\n"
        "/admin_dedupe\n"
        "/admin_credit_ledger (Admin)\n"
        "/help"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # לא עונים בלופ על כל דבר; רק הודעה קצרה
    await update.effective_message.reply_text("⚠️ פקודה לא מוכרת. נסה /help")


def get_tg_app() -> Application:
    global _tg_app
    if _tg_app is None:
        _tg_app = Application.builder().token(BOT_TOKEN).build()
    return _tg_app


def ensure_handlers() -> None:
    global _handlers_ready
    if _handlers_ready:
        return

    app = get_tg_app()

    # רישום Handlers פעם אחת בלבד (לא בתוך כל webhook)
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    # Unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    _handlers_ready = True


async def process_webhook(update_dict: Dict[str, Any]) -> None:
    """
    Called by FastAPI webhook endpoint.
    Must not raise (main.py catches anyway), and must not reference undefined vars.
    """
    ensure_handlers()
    app = get_tg_app()

    # Convert dict -> Update and process
    upd = Update.de_json(update_dict, app.bot)
    if upd is None:
        return

    await app.process_update(upd)
