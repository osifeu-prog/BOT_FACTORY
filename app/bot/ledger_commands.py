from __future__ import annotations

from decimal import Decimal
from telegram import Update
from telegram.ext import ContextTypes

from app.core.ledger import get_balance, get_history


async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id if update.effective_user else None
    if tid is None:
        return

    bal = get_balance(int(tid), asset="SLH")
    await update.effective_message.reply_text(
        f"💰 SLH Balance (Ledger)\n"
        f"{bal:.4f} SLH"
    )


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = update.effective_user.id if update.effective_user else None
    if tid is None:
        return

    rows = get_history(int(tid), limit=10, asset="SLH")
    if not rows:
        await update.effective_message.reply_text("📜 History (Ledger)\nNo transactions yet.")
        return

    lines = ["📜 History (Ledger) — last 10", ""]
    for r in rows:
        other = f" ↔ {r.other_party}" if r.other_party is not None else ""
        memo = f" — {r.memo}" if r.memo else ""
        lines.append(f"[{r.created_at}] {r.direction} {Decimal(r.amount):.4f} {r.asset} (kind={r.kind}{other}){memo}")
    await update.effective_message.reply_text("\n".join(lines))