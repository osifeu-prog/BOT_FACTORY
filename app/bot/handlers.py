from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "✅ BOT_FACTORY is alive.\n"
        "Commands:\n"
        "/menu\n"
        "/history\n"
        "/referrals"
    )

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📋 Menu\n"
        "• /history — last internal ledger entries (to wire next)\n"
        "• /referrals — referral summary (to wire next)"
    )

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🧾 History\n"
        "Stable placeholder. Next: connect to your ledger tables."
    )

async def referrals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "👥 Referrals\n"
        "Stable placeholder. Next: connect to referrals table + admin report."
    )