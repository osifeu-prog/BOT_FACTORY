"""create_staking_engine_tables_fix

Revision ID: 9d4ba33ac368
Revises: 110c3e7c7a78
Create Date: 2026-01-09

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "9d4ba33ac368"
down_revision = "110c3e7c7a78"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(name, schema="public")


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


def upgrade() -> None:
    # ---- staking_pools ----
    if not _has_table("staking_pools"):
        op.create_table(
            "staking_pools",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("asset_symbol", sa.String(length=32), nullable=False),
            sa.Column("reward_asset_symbol", sa.String(length=32), nullable=False),
            sa.Column("apy_bps", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("lock_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("early_withdraw_penalty_bps", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("min_stake", sa.Numeric(38, 18), nullable=True),
            sa.Column("max_stake", sa.Numeric(38, 18), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
            sa.CheckConstraint("apy_bps >= 0", name="ck_staking_pools_apy_bps_nonneg"),
            sa.CheckConstraint("lock_seconds >= 0", name="ck_staking_pools_lock_seconds_nonneg"),
            sa.CheckConstraint(
                "early_withdraw_penalty_bps >= 0 AND early_withdraw_penalty_bps <= 10000",
                name="ck_staking_pools_penalty_bps_range",
            ),
        )

    _exec("CREATE UNIQUE INDEX IF NOT EXISTS ix_staking_pools_code ON public.staking_pools (code)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_pools_asset_symbol ON public.staking_pools (asset_symbol)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_pools_is_active ON public.staking_pools (is_active)")

    # ---- staking_positions ----
    if not _has_table("staking_positions"):
        op.create_table(
            "staking_positions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("pool_id", sa.String(length=36), sa.ForeignKey("staking_pools.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("principal_amount", sa.Numeric(38, 18), nullable=False),
            sa.Column("state", sa.String(length=16), nullable=False, server_default=sa.text("'CREATED'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
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

    _exec("CREATE INDEX IF NOT EXISTS ix_staking_positions_user_telegram_id ON public.staking_positions (user_telegram_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_positions_state ON public.staking_positions (state)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_positions_user_state ON public.staking_positions (user_telegram_id, state)")

    # ---- staking_rewards ----
    if not _has_table("staking_rewards"):
        op.create_table(
            "staking_rewards",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("position_id", sa.String(length=36), sa.ForeignKey("staking_positions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reward_type", sa.String(length=16), nullable=False),
            sa.Column("amount", sa.Numeric(38, 18), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("meta", JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
            sa.CheckConstraint("amount >= 0", name="ck_staking_rewards_amount_nonneg"),
        )

    _exec("CREATE INDEX IF NOT EXISTS ix_staking_rewards_position_id ON public.staking_rewards (position_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_rewards_reward_type ON public.staking_rewards (reward_type)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_rewards_period_end ON public.staking_rewards (period_end)")

    # ---- staking_events ----
    if not _has_table("staking_events"):
        op.create_table(
            "staking_events",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("pool_id", sa.String(length=36), nullable=True),
            sa.Column("position_id", sa.String(length=36), nullable=True),
            sa.Column("request_id", sa.String(length=36), nullable=True),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("timezone('utc', now())")),
            sa.Column("actor_type", sa.String(length=16), nullable=False, server_default=sa.text("'SYSTEM'")),
            sa.Column("actor_id", sa.String(length=64), nullable=True),
            sa.Column("amount", sa.Numeric(38, 18), nullable=True),
            sa.Column("details", JSONB(), nullable=True),
            sa.CheckConstraint("event_type <> ''", name="ck_staking_events_type_nonempty"),
        )

    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_event_type ON public.staking_events (event_type)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_user_telegram_id ON public.staking_events (user_telegram_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_pool_id ON public.staking_events (pool_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_position_id ON public.staking_events (position_id)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_occurred_at ON public.staking_events (occurred_at)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_user_time ON public.staking_events (user_telegram_id, occurred_at)")
    _exec("CREATE INDEX IF NOT EXISTS ix_staking_events_position_time ON public.staking_events (position_id, occurred_at)")
    _exec("CREATE UNIQUE INDEX IF NOT EXISTS uq_staking_events_request_id ON public.staking_events (request_id)")


def downgrade() -> None:
    _exec("DROP INDEX IF EXISTS public.uq_staking_events_request_id")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_position_time")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_user_time")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_occurred_at")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_position_id")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_pool_id")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_user_telegram_id")
    _exec("DROP INDEX IF EXISTS public.ix_staking_events_event_type")
    op.execute(sa.text("DROP TABLE IF EXISTS public.staking_events"))

    _exec("DROP INDEX IF EXISTS public.ix_staking_rewards_period_end")
    _exec("DROP INDEX IF EXISTS public.ix_staking_rewards_reward_type")
    _exec("DROP INDEX IF EXISTS public.ix_staking_rewards_position_id")
    op.execute(sa.text("DROP TABLE IF EXISTS public.staking_rewards"))

    _exec("DROP INDEX IF EXISTS public.ix_staking_positions_user_state")
    _exec("DROP INDEX IF EXISTS public.ix_staking_positions_state")
    _exec("DROP INDEX IF EXISTS public.ix_staking_positions_user_telegram_id")
    op.execute(sa.text("DROP TABLE IF EXISTS public.staking_positions"))

    _exec("DROP INDEX IF EXISTS public.ix_staking_pools_is_active")
    _exec("DROP INDEX IF EXISTS public.ix_staking_pools_asset_symbol")
    _exec("DROP INDEX IF EXISTS public.ix_staking_pools_code")
    op.execute(sa.text("DROP TABLE IF EXISTS public.staking_pools"))