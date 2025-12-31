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

# أ—â€چأ—آ¦أ—â€¢أ—آ¤أ—â€‌ أ—آ©أ—â€چأ—â€¢أ—â€™أ—â€œأ—آ¨أ—â„¢أ—â€Œ أ—â€کأ—طŒأ—â€کأ—â„¢أ—â€کأ—â€‌ / settings أ—آ©أ—إ“أ—ع‘
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is empty; Telegram webhook processing will fail until set.")

_tg_app: Optional[Application] = None
_handlers_ready: bool = False


# ----------------------------
# Handlers (أ—â€چأ—â„¢أ—آ أ—â„¢أ—â€چأ—â€¢أ—â€Œ أ—â€کأ—ع©أ—â€¢أ—â€”)
# ----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "أ—â€کأ—آ¨أ—â€¢أ—ع‘ أ—â€‌أ—â€کأ—ع¯ أ—إ“-SLH Investor Gateway.\n\n"
        "أ—آ¤أ—آ§أ—â€¢أ—â€œأ—â€¢أ—ع¾ أ—â€“أ—â€چأ—â„¢أ—آ أ—â€¢أ—ع¾:\n"
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
    # أ—إ“أ—ع¯ أ—آ¢أ—â€¢أ—آ أ—â„¢أ—â€Œ أ—â€کأ—إ“أ—â€¢أ—آ¤ أ—آ¢أ—إ“ أ—â€؛أ—إ“ أ—â€œأ—â€کأ—آ¨; أ—آ¨أ—آ§ أ—â€‌أ—â€¢أ—â€œأ—آ¢أ—â€‌ أ—آ§أ—آ¦أ—آ¨أ—â€‌
    await update.effective_message.reply_text("أ¢ع‘آ أ¯آ¸عˆ أ—آ¤أ—آ§أ—â€¢أ—â€œأ—â€‌ أ—إ“أ—ع¯ أ—â€چأ—â€¢أ—â€؛أ—آ¨أ—ع¾. أ—آ أ—طŒأ—â€‌ /help")


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

    # أ—آ¨أ—â„¢أ—آ©أ—â€¢أ—â€Œ Handlers أ—آ¤أ—آ¢أ—â€Œ أ—ع¯أ—â€”أ—ع¾ أ—â€کأ—إ“أ—â€کأ—â€œ (أ—إ“أ—ع¯ أ—â€کأ—ع¾أ—â€¢أ—ع‘ أ—â€؛أ—إ“ webhook)
    _TG_APP.add_handler(CommandHandler("start", start_cmd))
    _TG_APP.add_handler(CommandHandler("help", help_cmd))

    # Unknown commands
    if _TG_APP is not None and not getattr(_TG_APP, "_unknown_cmd_installed", False):
        if _TG_APP is not None and not getattr(_TG_APP, "_unknown_cmd_installed", False):
            _TG_APP.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))
            setattr(_TG_APP, "_unknown_cmd_installed", True)
        setattr(_TG_APP, "_unknown_cmd_installed", True)
    _handlers_ready = True


async def process_webhook(update_dict: Dict[str, Any]) -> None:
    # --- simple in-memory dedupe (10 min) ---
    import time as _time
    _seen = globals().setdefault("_seen_updates", {})  # {update_id: ts}
    _now = _time.time()
    for _k, _ts in list(_seen.items()):
        if _now - _ts > 600:
            _seen.pop(_k, None)
    _uid = update_dict.get("update_id")
    if _uid is not None:
        if _uid in _seen:
            return
        _seen[_uid] = _now
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
