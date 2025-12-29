from __future__ import annotations

import os
from typing import Optional, Tuple

import psycopg2
from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.telegram_updates import ensure_telegram_updates_table


def _is_admin(user_id: Optional[int]) -> bool:
    admin_raw = getattr(settings, "ADMIN_USER_ID", None) or os.getenv("ADMIN_USER_ID")
    if not admin_raw:
        return False
    # allow "123" or "123,456"
    raw = str(admin_raw).strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for p in parts:
        try:
            if int(p) == int(user_id or 0):
                return True
        except Exception:
            if p == str(user_id or ""):
                return True
    return False


def _connect():
    dsn = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", None)
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    pw = os.getenv("PGPASSWORD")
    return psycopg2.connect(dsn, password=pw) if pw else psycopg2.connect(dsn)


def get_dedupe_stats() -> Tuple[int, Optional[tuple]]:
    ensure_telegram_updates_table()

    conn = _connect()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM telegram_updates;")
            count_rows = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT update_id, received_at, chat_id, user_id, kind
                FROM telegram_updates
                ORDER BY id DESC
                LIMIT 1;
                """
            )
            last_row = cur.fetchone()
            return count_rows, last_row
        finally:
            cur.close()
    finally:
        conn.close()


async def admin_dedupe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    if not _is_admin(uid):
        await update.effective_message.reply_text("⛔ אין הרשאה. (ADMIN בלבד)")
        return

    count_rows, last_row = get_dedupe_stats()

    lines = []
    lines.append("🧩 Dedupe Status (telegram_updates)")
    lines.append(f"• rows: {count_rows}")

    if last_row:
        update_id, received_at, chat_id, user_id, kind = last_row
        lines.append("• last:")
        lines.append(f"  - update_id: {update_id}")
        lines.append(f"  - received_at: {received_at}")
        lines.append(f"  - chat_id: {chat_id}")
        lines.append(f"  - user_id: {user_id}")
        lines.append(f"  - kind: {kind}")
    else:
        lines.append("• last: (empty)")

    await update.effective_message.reply_text("\n".join(lines))