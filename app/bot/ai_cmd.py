from __future__ import annotations

import os
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    try:
        return uid is not None and int(uid) == int(settings.ADMIN_USER_ID)
    except Exception:
        return False


async def ai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /ai <prompt...>
    Admin-only. Uses OPENAI_API_KEY + OPENAI_MODEL.
    """
    if not _is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return

    prompt = " ".join(list(context.args or [])).strip()
    if not prompt:
        await update.effective_message.reply_text("Usage: /ai <prompt...>")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        await update.effective_message.reply_text("Missing OPENAI_API_KEY in environment.")
        return

    if OpenAI is None:
        await update.effective_message.reply_text("openai package not installed. Add openai>=1.0.0 to requirements.")
        return

    client = OpenAI(api_key=api_key)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise engineering assistant for the SLH ecosystem."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    text = (resp.choices[0].message.content or "").strip() or "(empty response)"
    if len(text) > 3500:
        text = text[:3500] + "\n…(truncated)"

    await update.effective_message.reply_text(text)