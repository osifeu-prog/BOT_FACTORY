from __future__ import annotations

import os
import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

log = logging.getLogger("bot_factory")

_TG_APP: Application | None = None

def env_str(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def get_tg_app() -> Application:
    global _TG_APP
    if _TG_APP is not None:
        return _TG_APP
    token = env_str("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN missing")
    _TG_APP = Application.builder().token(token).build()
    return _TG_APP

def _is_admin(telegram_id: int) -> bool:
    admin = env_str("ADMIN_USER_ID")
    if not admin:
        return False
    try:
        return int(admin) == int(telegram_id)
    except Exception:
        return False

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "עזרה / פקודות:\n\n"
        "/whoami  פרופיל טלגרם\n"
        "/balance  יתרת SLH (Ledger ב-Postgres)\n"
        "/history  היסטוריה (Ledger)\n"
        "/admin_dedupe  בדיקת dedupe ל-telegram_updates (Admin)\n"
        "/admin_credit_ledger <amount> [memo]  הזרקת SLH ל-Ledger (Admin)\n"
        "דוגמא: /admin_credit_ledger 1.00 Seed"
    )

async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if not u:
        return
    uname = f"@{u.username}" if getattr(u, "username", None) else "-"
    await update.effective_message.reply_text(
        "Your SLH Investor Profile\n\n"
        f"Telegram ID: {u.id}\n"
        f"Username: {uname}"
    )

def _db_try_import():
    try:
        from app.core.ledger import get_balance, get_history, admin_credit  # type: ignore
        return {"get_balance": get_balance, "get_history": get_history, "admin_credit": admin_credit}
    except Exception:
        return None

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if not u:
        return
    db = _db_try_import()
    if not db:
        await update.effective_message.reply_text("⚠️ Ledger DB helpers not available.")
        return
    try:
        bal = db["get_balance"](telegram_id=int(u.id))
        await update.effective_message.reply_text(f"💰 SLH Balance (Ledger)\n{bal}")
    except Exception as e:
        log.exception("balance failed")
        await update.effective_message.reply_text(f"⚠️ Balance error: {type(e).__name__}")

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if not u:
        return
    db = _db_try_import()
    if not db:
        await update.effective_message.reply_text("⚠️ Ledger DB helpers not available.")
        return
    try:
        rows = db["get_history"](telegram_id=int(u.id), limit=10)
        lines = [str(r) for r in (rows or [])]
        text = "📜 History (Ledger) — last 10\n\n" + ("\n".join(lines) if lines else "(empty)")
        await update.effective_message.reply_text(text)
    except Exception as e:
        log.exception("history failed")
        await update.effective_message.reply_text(f"⚠️ History error: {type(e).__name__}")

async def admin_dedupe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if not u or not _is_admin(u.id):
        return
    try:
        from app.core.telegram_updates import dedupe_status  # type: ignore
        await update.effective_message.reply_text(str(dedupe_status()))
    except Exception as e:
        log.exception("dedupe_status failed")
        await update.effective_message.reply_text(f"⚠️ dedupe error: {type(e).__name__}")

async def admin_credit_ledger_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = update.effective_user
    if not u or not _is_admin(u.id):
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/admin_credit_ledger <amount> [memo]\n"
            "/admin_credit_ledger <telegram_id> <amount> [memo]\n"
            "Example:\n"
            "/admin_credit_ledger 1000 Seed"
        )
        return

    target_id = int(u.id)
    memo = None
    if len(args) >= 2:
        try:
            target_id = int(args[0])
            amount_s = args[1]
            memo = " ".join(args[2:]) if len(args) > 2 else None
        except Exception:
            amount_s = args[0]
            memo = " ".join(args[1:]) if len(args) > 1 else None
    else:
        amount_s = args[0]

    try:
        amt = Decimal(amount_s)
    except (InvalidOperation, TypeError):
        await update.effective_message.reply_text("❌ Invalid amount.")
        return

    db = _db_try_import()
    if not db:
        await update.effective_message.reply_text("⚠️ Ledger DB helpers not available.")
        return
    try:
        tx_id = db["admin_credit"](telegram_id=int(target_id), amount=amt, memo=memo)
        await update.effective_message.reply_text(
            "✅ Ledger credited\n"
            f"telegram_id: {target_id}\n"
            f"amount: {amt:.4f} SLH\n"
            f"tx_id: {tx_id}"
        )
    except Exception as e:
        log.exception("admin_credit failed")
        await update.effective_message.reply_text(f"⚠️ credit error: {type(e).__name__}")

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("❓ פקודה לא מוכרת. נסה /help")

def ensure_handlers() -> None:
    app = get_tg_app()
    if getattr(app, "_handlers_installed", False):
        return
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("admin_dedupe", admin_dedupe_cmd))
    app.add_handler(CommandHandler("admin_credit_ledger", admin_credit_ledger_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_cmd))
    setattr(app, "_handlers_installed", True)

def initialize_bot() -> None:
    ensure_handlers()

async def process_webhook(update_dict: Dict[str, Any]) -> None:
    ensure_handlers()
    app = get_tg_app()
    upd = Update.de_json(update_dict, app.bot)
    if upd is None:
        return
    await app.process_update(upd)