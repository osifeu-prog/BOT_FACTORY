from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.ledger import credit


def _is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    try:
        return uid is not None and int(uid) == int(settings.ADMIN_USER_ID)
    except Exception:
        return False


async def admin_credit_ledger_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin_credit_ledger <amount> [memo...]
    /admin_credit_ledger <telegram_id> <amount> [memo...]

    Examples:
      /admin_credit_ledger 1000 Seed
      /admin_credit_ledger 224223270 1000 Seed
    """
    if not _is_admin(update):
        await update.effective_message.reply_text("⛔ Admin only.")
        return

    args = list(context.args or [])
    if not args:
        await update.effective_message.reply_text(
            "Usage:\n"
            "/admin_credit_ledger <amount> [memo]\n"
            "/admin_credit_ledger <telegram_id> <amount> [memo]"
        )
        return

    tid: Optional[int] = None
    amount_s: Optional[str] = None
    memo: Optional[str] = None

    # If first arg looks like telegram_id and we have at least 2 args -> (tid, amount)
    if len(args) >= 2 and args[0].isdigit():
        tid = int(args[0])
        amount_s = args[1]
        memo = " ".join(args[2:]).strip() or None
    else:
        # (amount) -> credit self
        tid = update.effective_user.id if update.effective_user else None
        amount_s = args[0]
        memo = " ".join(args[1:]).strip() or None

    if tid is None:
        await update.effective_message.reply_text("Could not determine telegram_id.")
        return

    try:
        amt = Decimal(amount_s)
        if amt <= 0:
            raise ValueError("amount must be > 0")
    except (InvalidOperation, ValueError):
        await update.effective_message.reply_text("Invalid amount. Example: /admin_credit_ledger 1000 Seed")
        return

    tx_id = credit(
        int(tid),
        amt,
        kind="admin_credit",
        memo=memo,
        ref_update_id=(update.update_id if update else None),
        asset="SLH",
    )

    await update.effective_message.reply_text(
        "✅ Ledger credited\n"
        f"telegram_id: {tid}\n"
        f"amount: {amt:.4f} SLH\n"
        f"tx_id: {tx_id}"
    )