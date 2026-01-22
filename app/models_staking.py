from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base


class StakingPool(Base):
    __tablename__ = "staking_pools"

    id = Column(String(36), primary_key=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    asset_symbol = Column(String(32), nullable=False, index=True)
    reward_asset_symbol = Column(String(32), nullable=False)

    apy_bps = Column(Integer, nullable=False, server_default="0")
    lock_seconds = Column(Integer, nullable=False, server_default="0")
    early_withdraw_penalty_bps = Column(Integer, nullable=False, server_default="0")

    min_stake = Column(Numeric(38, 18), nullable=True)
    max_stake = Column(Numeric(38, 18), nullable=True)

    is_active = Column(Boolean, nullable=False, server_default="true", index=True)

    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.timezone("utc", func.now()))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.timezone("utc", func.now()))

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

    id = Column(String(36), primary_key=True)

    user_telegram_id = Column(BigInteger, nullable=False, index=True)
    pool_id = Column(String(36), ForeignKey("staking_pools.id", ondelete="RESTRICT"), nullable=False)

    principal_amount = Column(Numeric(38, 18), nullable=False)
    state = Column(String(16), nullable=False, server_default="CREATED", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.timezone("utc", func.now()))
    activated_at = Column(DateTime(timezone=True), nullable=True)
    matures_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    last_accrual_at = Column(DateTime(timezone=True), nullable=True)

    total_reward_accrued = Column(Numeric(38, 18), nullable=False, server_default="0")
    total_reward_claimed = Column(Numeric(38, 18), nullable=False, server_default="0")

    version = Column(Integer, nullable=False, server_default="1")

    __table_args__ = (
        CheckConstraint("principal_amount > 0", name="ck_staking_positions_principal_positive"),
        CheckConstraint("total_reward_accrued >= 0", name="ck_staking_positions_accrued_nonneg"),
        CheckConstraint("total_reward_claimed >= 0", name="ck_staking_positions_claimed_nonneg"),
        Index("ix_staking_positions_state", "state"),
        Index("ix_staking_positions_user_state", "user_telegram_id", "state"),
        Index("ix_staking_positions_user_telegram_id", "user_telegram_id"),
    )


class StakingReward(Base):
    __tablename__ = "staking_rewards"

    id = Column(String(36), primary_key=True)
    position_id = Column(String(36), ForeignKey("staking_positions.id", ondelete="CASCADE"), nullable=False, index=True)

    reward_type = Column(String(16), nullable=False, index=True)
    amount = Column(Numeric(38, 18), nullable=False)

    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True, index=True)

    meta = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.timezone("utc", func.now()))

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_staking_rewards_amount_nonneg"),
    )


class StakingEvent(Base):
    __tablename__ = "staking_events"

    id = Column(String(36), primary_key=True)

    event_type = Column(String(40), nullable=False, index=True)
    user_telegram_id = Column(BigInteger, nullable=False, index=True)

    pool_id = Column(String(36), nullable=True)
    position_id = Column(String(36), nullable=True, index=True)

    # autogen showed DB is VARCHAR(36)
    request_id = Column(String(36), nullable=True, unique=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.timezone("utc", func.now()), index=True)
    actor_type = Column(String(16), nullable=False, server_default="SYSTEM")
    actor_id = Column(String(64), nullable=True)

    amount = Column(Numeric(38, 18), nullable=True)
    details = Column(JSONB, nullable=True)

    __table_args__ = (
        # DB indexes
        Index("ix_staking_events_event_type", "event_type"),
        Index("ix_staking_events_occurred_at", "occurred_at"),
        Index("ix_staking_events_position_id", "position_id"),
        Index("ix_staking_events_position_time", "position_id", "occurred_at"),
        Index("ix_staking_events_user_telegram_id", "user_telegram_id"),
        Index("ix_staking_events_user_time", "user_telegram_id", "occurred_at"),
        # autogen said DB has this index and model was missing it:
        Index("ix_staking_events_pool_id", "pool_id"),
        CheckConstraint("event_type <> ''", name="ck_staking_events_type_nonempty"),
    )