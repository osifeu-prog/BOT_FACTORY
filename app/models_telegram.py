from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Index, Sequence
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    id = Column(BigInteger, Sequence("telegram_updates_id_seq"), primary_key=True)
    update_id = Column(BigInteger, nullable=True)
    telegram_user_id = Column(BigInteger, nullable=True)
    payload = Column(JSONB, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # DB index is (received_at DESC)
        Index("ix_telegram_updates_received_at", received_at.desc()),
    )