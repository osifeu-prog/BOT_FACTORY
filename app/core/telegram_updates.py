from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import os

import psycopg2


DDL_TABLE = """
CREATE TABLE IF NOT EXISTS telegram_updates (
  id BIGSERIAL PRIMARY KEY,
  update_id BIGINT NOT NULL UNIQUE,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  chat_id BIGINT NULL,
  user_id BIGINT NULL,
  kind TEXT NULL
);
"""

DDL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_telegram_updates_received_at
ON telegram_updates (received_at);
"""


def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return dsn


def ensure_telegram_updates_table() -> None:
    """
    Idempotent. Safe to call on every startup.
    """
    dsn = _dsn()
    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(DDL_TABLE)
            cur.execute(DDL_INDEX)
        finally:
            cur.close()
    finally:
        conn.close()


def _extract_chat_user_kind(payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    # best-effort, supports message / edited_message / callback_query / etc.
    chat_id: Optional[int] = None
    user_id: Optional[int] = None
    kind: Optional[str] = None

    if "message" in payload:
        kind = "message"
        msg = payload.get("message") or {}
    elif "edited_message" in payload:
        kind = "edited_message"
        msg = payload.get("edited_message") or {}
    elif "callback_query" in payload:
        kind = "callback_query"
        cb = payload.get("callback_query") or {}
        msg = cb.get("message") or {}
        # callback "from" is in cb
        fr = cb.get("from") or {}
        if isinstance(fr, dict):
            user_id = fr.get("id")
    else:
        kind = "other"
        msg = (
            payload.get("channel_post")
            or payload.get("edited_channel_post")
            or {}
        )

    if isinstance(msg, dict):
        chat = msg.get("chat") or {}
        fr = msg.get("from") or {}

        if isinstance(chat, dict):
            chat_id = chat.get("id")
        if user_id is None and isinstance(fr, dict):
            user_id = fr.get("id")

    return chat_id, user_id, kind


def register_update_once(payload: Dict[str, Any]) -> bool:
    """
    Returns True if update is NEW (inserted),
    False if it already exists (duplicate).
    """
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        # If Telegram ever sends something weird, don't block processing.
        return True

    chat_id, user_id, kind = _extract_chat_user_kind(payload)

    dsn = _dsn()
    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO telegram_updates (update_id, chat_id, user_id, kind)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (update_id) DO NOTHING
                RETURNING id;
                """,
                (update_id, chat_id, user_id, kind),
            )
            row = cur.fetchone()
            return row is not None
        finally:
            cur.close()
    finally:
        conn.close()