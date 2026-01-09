"""create_staking_engine_tables

Revision ID: 110c3e7c7a78
Revises: 20260101184108
Create Date: 2026-01-09 19:00:39.734980

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "110c3e7c7a78"
down_revision = "20260101184108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- staking_pools ---
    op.create_table(
        "staking_pools",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("asset_symbol", sa.String(length=32), nullable=False),
        sa.Column("reward_asset_symbol", sa.String(length=32), nullable=False),
        sa.Column("apy_bps", sa.Integer(), nullable=False, server_default=sa.text("0")),  # 1200 = 12.00%
        sa.Column("lock_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("early_withdraw_penalty_bps", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("min_stake", sa.Numeric(38, 18), nullable=True),
        sa.Column("max_stake", sa.Numeric(38, 18), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint("apy_bps >= 0", name="ck_staking_pools_apy_bps_nonneg"),
        sa.CheckConstraint("lock_seconds >= 0", name="ck_staking_pools_lock_seconds_nonneg"),
        sa.CheckConstraint(
            "early_withdraw_penalty_bps >= 0 AND early_withdraw_penalty_bps <= 10000",
            name="ck_staking_pools_penalty_bps_range",
        ),
    )

    # indexes (keep explicit for clarity & fast queries)
    op.create_index("ix_staking_pools_code", "staking_pools", ["code"], unique=True)
    op.create_index("ix_staking_pools_asset_symbol", "staking_pools", ["asset_symbol"], unique=False)
    op.create_index("ix_staking_pools_is_active", "staking_pools", ["is_active"], unique=False)

    # --- staking_positions ---
    op.create_table(
        "staking_positions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "pool_id",
            sa.String(length=36),
            sa.ForeignKey("staking_pools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False, server_default=sa.text("'CREATED'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("matures_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accrual_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_reward_accrued", sa.Numeric(38, 18), nullable=False, server_default=sa.text("0")),
        sa.Column("total_reward_claimed", sa.Numeric(38, 18), nullable=False, server_default=sa.text("0")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("principal_amount > 0", name="ck_staking_positions_principal_positive"),
        sa.CheckConstraint("total_reward_accrued >= 0", name="ck_staking_positions_accrued_nonneg"),
        sa.CheckConstraint("total_reward_claimed >= 0", name="ck_staking_positions_claimed_nonneg"),
    )

    op.create_index("ix_staking_positions_user_telegram_id", "staking_positions", ["user_telegram_id"], unique=False)
    op.create_index("ix_staking_positions_state", "staking_positions", ["state"], unique=False)
    op.create_index(
        "ix_staking_positions_user_state",
        "staking_positions",
        ["user_telegram_id", "state"],
        unique=False,
    )

    # --- staking_rewards ---
    op.create_table(
        "staking_rewards",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column(
            "position_id",
            sa.String(length=36),
            sa.ForeignKey("staking_positions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reward_type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(38, 18), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint("amount >= 0", name="ck_staking_rewards_amount_nonneg"),
    )

    op.create_index("ix_staking_rewards_position_id", "staking_rewards", ["position_id"], unique=False)
    op.create_index("ix_staking_rewards_reward_type", "staking_rewards", ["reward_type"], unique=False)
    op.create_index("ix_staking_rewards_period_end", "staking_rewards", ["period_end"], unique=False)

    # --- staking_events ---
    op.create_table(
        "staking_events",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("pool_id", sa.String(length=36), nullable=True),
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default=sa.text("'SYSTEM'")),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("amount", sa.Numeric(38, 18), nullable=True),
        sa.Column("details", JSONB(), nullable=True),
        sa.CheckConstraint("event_type <> ''", name="ck_staking_events_type_nonempty"),
    )

    op.create_index("ix_staking_events_event_type", "staking_events", ["event_type"], unique=False)
    op.create_index("ix_staking_events_user_telegram_id", "staking_events", ["user_telegram_id"], unique=False)
    op.create_index("ix_staking_events_pool_id", "staking_events", ["pool_id"], unique=False)
    op.create_index("ix_staking_events_position_id", "staking_events", ["position_id"], unique=False)
    op.create_index("ix_staking_events_occurred_at", "staking_events", ["occurred_at"], unique=False)
    op.create_index(
        "ix_staking_events_user_time",
        "staking_events",
        ["user_telegram_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_staking_events_position_time",
        "staking_events",
        ["position_id", "occurred_at"],
        unique=False,
    )

    # Keep request_id unique when provided (Postgres allows multiple NULLs under UNIQUE)
    op.create_unique_constraint("uq_staking_events_request_id", "staking_events", ["request_id"])


def downgrade() -> None:
    # --- staking_events ---
    op.drop_constraint("uq_staking_events_request_id", "staking_events", type_="unique")
    op.drop_index("ix_staking_events_position_time", table_name="staking_events")
    op.drop_index("ix_staking_events_user_time", table_name="staking_events")
    op.drop_index("ix_staking_events_occurred_at", table_name="staking_events")
    op.drop_index("ix_staking_events_position_id", table_name="staking_events")
    op.drop_index("ix_staking_events_pool_id", table_name="staking_events")
    op.drop_index("ix_staking_events_user_telegram_id", table_name="staking_events")
    op.drop_index("ix_staking_events_event_type", table_name="staking_events")
    op.drop_table("staking_events")

    # --- staking_rewards ---
    op.drop_index("ix_staking_rewards_period_end", table_name="staking_rewards")
    op.drop_index("ix_staking_rewards_reward_type", table_name="staking_rewards")
    op.drop_index("ix_staking_rewards_position_id", table_name="staking_rewards")
    op.drop_table("staking_rewards")

    # --- staking_positions ---
    op.drop_index("ix_staking_positions_user_state", table_name="staking_positions")
    op.drop_index("ix_staking_positions_state", table_name="staking_positions")
    op.drop_index("ix_staking_positions_user_telegram_id", table_name="staking_positions")
    op.drop_table("staking_positions")

    # --- staking_pools ---
    op.drop_index("ix_staking_pools_is_active", table_name="staking_pools")
    op.drop_index("ix_staking_pools_asset_symbol", table_name="staking_pools")
    op.drop_index("ix_staking_pools_code", table_name="staking_pools")
    op.drop_table("staking_pools")
