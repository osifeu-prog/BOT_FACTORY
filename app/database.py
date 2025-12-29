from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

def db_init() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS telegram_updates (
      id BIGSERIAL PRIMARY KEY,
      update_id BIGINT NOT NULL UNIQUE,
      received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      chat_id BIGINT NULL,
      user_id BIGINT NULL,
      kind TEXT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_telegram_updates_received_at ON telegram_updates (received_at);
    """
    with engine.begin() as conn:
        for stmt in [s.strip() for s in ddl.split(";") if s.strip()]:
            conn.execute(text(stmt))