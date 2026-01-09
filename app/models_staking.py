from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid.uuid4())


class StakingPositionState(str, enum.Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"
    CANCELLED = "CANCELLED"


class StakingRewardType(str, enum.Enum):
    ACCRUAL = "ACCRUAL"
    CLAIM = "CLAIM"
    ADJUSTMENT = "ADJUSTMENT"


class StakingActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"


class StakingEventType(str, enum.Enum):
    POSITION_CREATED = "POSITION_CREATED"
    POSITION_ACTIVATED = "POSITION_ACTIVATED"
    ACCRUAL_RECORDED = "ACCRUAL_RECORDED"
    REWARD_CLAIMED = "REWARD_CLAIMED"
    UNSTAKE_REQUESTED = "UNSTAKE_REQUESTED"
    POSITION_WITHDRAWN = "POSITION_WITHDRAWN"
    POSITION_COMPLETED = "POSITION_COMPLETED"
    POSITION_CANCELLED = "POSITION_CANCELLED"


class StakingPool(Base):
    __tablename__ = "staking_pools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset_symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reward_asset_symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    apy_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 1200 = 12.00%
    lock_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_withdraw_penalty_bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    min_stake: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    max_stake: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )

    positions: Mapped[list["StakingPosition"]] = relationship(back_populates="pool", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("apy_bps >= 0", name="ck_staking_pools_apy_bps_nonneg"),
        CheckConstraint("lock_seconds >= 0", name="ck_staking_pools_lock_seconds_nonneg"),
        CheckConstraint(
            "early_withdraw_penalty_bps >= 0 AND early_withdraw_penalty_bps <= 10000",
            name="ck_staking_pools_penalty_bps_range",
        ),
    )


class StakingPosition(Base):
    __tablename__ = "staking_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)

    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pool_id: Mapped[str] = mapped_column(String(36), ForeignKey("staking_pools.id", ondelete="RESTRICT"), nullable=False)

    principal_amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)

    state: Mapped[str] = mapped_column(String(16), nullable=False, default=StakingPositionState.CREATED.value, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    matures_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_accrual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    total_reward_accrued: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))
    total_reward_claimed: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False, default=Decimal("0"))

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    pool: Mapped["StakingPool"] = relationship(back_populates="positions")
    rewards: Mapped[list["StakingReward"]] = relationship(back_populates="position", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("principal_amount > 0", name="ck_staking_positions_principal_positive"),
        CheckConstraint("total_reward_accrued >= 0", name="ck_staking_positions_accrued_nonneg"),
        CheckConstraint("total_reward_claimed >= 0", name="ck_staking_positions_claimed_nonneg"),
        Index("ix_staking_positions_user_state", "user_telegram_id", "state"),
    )


class StakingReward(Base):
    __tablename__ = "staking_rewards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    position_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("staking_positions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    reward_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )

    position: Mapped["StakingPosition"] = relationship(back_populates="rewards")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_staking_rewards_amount_nonneg"),
        Index("ix_staking_rewards_period_end", "period_end"),
    )


class StakingEvent(Base):
    __tablename__ = "staking_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)

    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    user_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    pool_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("timezone('utc', now())"),
        index=True,
    )

    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default=StakingActorType.SYSTEM.value)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    amount: Mapped[Decimal | None] = mapped_column(Numeric(38, 18), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_staking_events_user_time", "user_telegram_id", "occurred_at"),
        Index("ix_staking_events_position_time", "position_id", "occurred_at"),
        CheckConstraint("event_type <> ''", name="ck_staking_events_type_nonempty"),
    )