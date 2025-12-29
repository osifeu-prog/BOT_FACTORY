from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

async def unknown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Always respond so we can see missing handlers immediately
    txt = update.effective_message.text if update.effective_message else ""
    await update.effective_message.reply_text(f"❓ Unknown command: {txt}")