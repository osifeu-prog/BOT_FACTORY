from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.utcnow()


class Deposit(Base):
    __tablename__ = "deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    amount_ils: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(32), default="bank", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)  # pending/confirmed/rejected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SLHLedger(Base):
    __tablename__ = "slh_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    amount_slh: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # deposit_reward/redeem/admin_adjust/...
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # deposit/redeem/...
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class RedemptionRequest(Base):
    __tablename__ = "redemption_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)

    slh_amount: Mapped[Decimal] = mapped_column(Numeric(28, 8), nullable=False)
    target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="requested", nullable=False)  # requested/approved/paid/rejected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by_admin: Mapped[int | None] = mapped_column(Integer, nullable=True)


Index("ix_slh_ledger_ref", SLHLedger.ref_type, SLHLedger.ref_id)