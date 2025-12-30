import os
import json
import hashlib
import logging
from typing import Any, Dict

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
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
    finally:
        conn.close()

def register_update_once(update: Any) -> bool:
    """
    Dedup Telegram updates (best-effort).
    Returns True if this update was newly registered, False if already seen.

    - If not using Postgres: returns True (no dedup in sqlite/local mode).
    - If Postgres: uses telegram_updates table unique constraint.
    """
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    if not dsn or not _is_postgres(dsn):
        return True  # local mode: do not block anything

    # Get update_id and payload safely
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        # fallback: hash payload to avoid crashing
        payload = {"repr": repr(update)}
        update_id = int(hashlib.sha256(repr(update).encode("utf-8")).hexdigest()[:15], 16)

    # Try to serialize payload
    try:
        if hasattr(update, "to_dict"):
            payload_obj: Dict[str, Any] = update.to_dict()
        else:
            payload_obj = json.loads(json.dumps(update, default=str))
    except Exception:
        payload_obj = {"repr": repr(update)}

    try:
        import psycopg2
        from psycopg2.extras import Json
    except Exception as e:
        log.warning("psycopg2 missing, cannot dedup updates: %s", e)
        return True

    sql = "INSERT INTO telegram_updates (update_id, payload) VALUES (%s, %s) ON CONFLICT (update_id) DO NOTHING;"
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, (int(update_id), Json(payload_obj)))
                # rowcount==1 -> inserted, 0 -> conflict
                return cur.rowcount == 1
    except Exception as e:
        log.warning("register_update_once failed (allowing update): %s", e)
        return True
    finally:
        conn.close()