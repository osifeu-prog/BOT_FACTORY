# app/bot/investor_wallet_bot.py
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.core.config import settings

# Optional command modules (we keep the bot alive even if one is missing)
try:
    from app.bot.ledger_commands import balance_cmd, history_cmd
except Exception:  # pragma: no cover
    balance_cmd = None
    history_cmd = None

try:
    from app.bot.admin_dedupe import admin_dedupe_cmd
except Exception:  # pragma: no cover
    admin_dedupe_cmd = None

try:
    from app.bot.unknown_cmd import unknown_cmd
except Exception:  # pragma: no cover
    unknown_cmd = None

log = logging.getLogger("bot")

_TG_APP: Optional[Application] = None


async def _start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "ברוך הבא ל-SLH Investor Gateway.\n\n"
        "פקודות:\n"
        "/whoami\n"
        "/balance\n"
        "/history\n"
        "/admin_dedupe\n"
        "/help"
    )


async def _help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "עזרה:\n"
        "/whoami – פרופיל טלגרם בסיסי\n"
        "/balance – יתרה מה-Ledger (Postgres)\n"
        "/history – היסטוריה מה-Ledger (Postgres)\n"
        "/admin_dedupe – סטטוס הטבלה telegram_updates (Admin)\n"
    )


async def _whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tid = user.id if user else None
    uname = ("@" + user.username) if (user and user.username) else "(no username)"
    await update.effective_message.reply_text(
        "Your SLH Investor Profile\n\n"
        f"Telegram ID: {tid}\n"
        f"Username: {uname}\n"
    )


def _require_cmd(fn, name: str):
    async def _missing(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text(
            f"⚠️ הפקודה {name} עדיין לא זמינה (מודול חסר/שגוי)."
        )

    return fn if fn is not None else _missing


def build_application() -> Application:
    app = Application.builder().token(settings.BOT_TOKEN).build()

    # core
    app.add_handler(CommandHandler("start", _start_cmd))
    app.add_handler(CommandHandler("help", _help_cmd))
    app.add_handler(CommandHandler("whoami", _whoami_cmd))

    # ledger wiring (REAL)
    app.add_handler(CommandHandler("balance", _require_cmd(balance_cmd, "/balance")))
    app.add_handler(CommandHandler("history", _require_cmd(history_cmd, "/history")))

    # admin / debug
    app.add_handler(
        CommandHandler("admin_dedupe", _require_cmd(admin_dedupe_cmd, "/admin_dedupe"))
    )

    # unknown commands (debug-friendly)
    if unknown_cmd is not None:
        app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))

    return app


async def initialize_bot() -> None:
    global _TG_APP
    if _TG_APP is not None:
        return
    _TG_APP = build_application()
    await _TG_APP.initialize()
    log.info("Telegram application initialized")


async def process_webhook(payload: Dict[str, Any]) -> None:
    """
    Called from FastAPI /webhook/telegram endpoint.
    """
    if _TG_APP is None:
        await initialize_bot()

    assert _TG_APP is not None
    update = Update.de_json(payload, _TG_APP.bot)
    await _TG_APP.process_update(update)
