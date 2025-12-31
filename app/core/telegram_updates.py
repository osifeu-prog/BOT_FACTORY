import os
import logging
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger(__name__)


def _is_postgres(dsn: str) -> bool:
    dsn = (dsn or "").strip().lower()
    return dsn.startswith("postgres://") or dsn.startswith("postgresql://") or dsn.startswith("postgres")


def ensure_telegram_updates_table() -> None:
    """
    Ensures the telegram_updates table exists.
    - Local dev (sqlite or missing DATABASE_URL): NO-OP.
    - Production (Postgres): create table if needed.
    """
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn or not _is_postgres(dsn):
        return

    try:
        import psycopg2
    except Exception as e:
        log.warning("psycopg2 not available, skipping telegram_updates table init: %s", e)
        return

    ddl = """
    CREATE TABLE IF NOT EXISTS telegram_updates (
      id BIGSERIAL PRIMARY KEY,
      update_id BIGINT UNIQUE NOT NULL,
      payload JSONB NOT NULL,
      chat_id BIGINT,
      user_id BIGINT,
      kind TEXT,
      received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_telegram_updates_update_id ON telegram_updates(update_id);
    CREATE INDEX IF NOT EXISTS idx_telegram_updates_received_at ON telegram_updates(received_at);
    CREATE INDEX IF NOT EXISTS idx_telegram_updates_chat_id ON telegram_updates(chat_id);
    CREATE INDEX IF NOT EXISTS idx_telegram_updates_user_id ON telegram_updates(user_id);
    """

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
    finally:
        conn.close()


def _extract_update_fields(payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """
    Extract chat_id, user_id, kind from Telegram update payload.
    Works for common update types: message, edited_message, callback_query, channel_post, etc.
    """
    if not isinstance(payload, dict):
        return None, None, None

    # Determine kind = first top-level key that looks like an update type
    kind = None
    for k, v in payload.items():
        if k in ("update_id",):
            continue
        if isinstance(v, dict):
            kind = k
            break

    obj = payload.get(kind) if kind else None
    if not isinstance(obj, dict):
        obj = payload.get("message") if isinstance(payload.get("message"), dict) else None

    chat_id = None
    user_id = None

    chat = obj.get("chat") if isinstance(obj, dict) else None
    if isinstance(chat, dict):
        chat_id = chat.get("id")

    frm = obj.get("from") if isinstance(obj, dict) else None
    if isinstance(frm, dict):
        user_id = frm.get("id")

    if kind == "callback_query":
        cb = payload.get("callback_query")
        if isinstance(cb, dict):
            frm2 = cb.get("from")
            if isinstance(frm2, dict) and user_id is None:
                user_id = frm2.get("id")
            msg2 = cb.get("message")
            if isinstance(msg2, dict) and chat_id is None:
                chat2 = msg2.get("chat")
                if isinstance(chat2, dict):
                    chat_id = chat2.get("id")

    try:
        chat_id = int(chat_id) if chat_id is not None else None
    except Exception:
        chat_id = None

    try:
        user_id = int(user_id) if user_id is not None else None
    except Exception:
        user_id = None

    kind = str(kind) if kind else None
    return chat_id, user_id, kind


def register_update_once(update_dict: Dict[str, Any]) -> bool:
    """
    Returns True if this update was newly registered, False if already seen.

    - If not using Postgres: returns True (no dedup in sqlite/local mode).
    - If Postgres: uses telegram_updates table unique constraint.
    """
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn or not _is_postgres(dsn):
        return True

    try:
        import psycopg2
        from psycopg2.extras import Json
    except Exception as e:
        log.warning("psycopg2 missing, cannot dedup updates: %s", e)
        return True

    try:
        update_id = int(update_dict.get("update_id"))
    except Exception:
        return True

    chat_id, user_id, kind = _extract_update_fields(update_dict)

    sql = """
    INSERT INTO telegram_updates (update_id, payload, chat_id, user_id, kind)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (update_id) DO NOTHING;
    """

    try:
        conn = psycopg2.connect(dsn)
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (update_id, Json(update_dict), chat_id, user_id, kind))
                    return cur.rowcount == 1
        finally:
            conn.close()
    except Exception as e:
        log.warning("register_update_once failed (allowing update): %s", e)
        return True