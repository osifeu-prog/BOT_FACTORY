"""force_create_staking_tables_sql

Revision ID: 46be64a69648
Revises: 9d4ba33ac368
Create Date: 2026-01-10
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "46be64a69648"
down_revision = "9d4ba33ac368"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.staking_pools (
        id VARCHAR(36) PRIMARY KEY,
        code VARCHAR(64) NOT NULL UNIQUE,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        asset_symbol VARCHAR(32) NOT NULL,
        reward_asset_symbol VARCHAR(32) NOT NULL,
        apy_bps INTEGER NOT NULL DEFAULT 0,
        lock_seconds INTEGER NOT NULL DEFAULT 0,
        early_withdraw_penalty_bps INTEGER NOT NULL DEFAULT 0,
        min_stake NUMERIC(38,18),
        max_stake NUMERIC(38,18),
        is_active BOOLEAN NOT NULL DEFAULT true,
        starts_at TIMESTAMPTZ,
        ends_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
    );

    CREATE TABLE IF NOT EXISTS public.staking_positions (
        id VARCHAR(36) PRIMARY KEY,
        user_telegram_id BIGINT NOT NULL,
        pool_id VARCHAR(36) NOT NULL REFERENCES public.staking_pools(id),
        principal_amount NUMERIC(38,18) NOT NULL,
        state VARCHAR(16) NOT NULL DEFAULT 'CREATED',
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        activated_at TIMESTAMPTZ,
        matures_at TIMESTAMPTZ,
        closed_at TIMESTAMPTZ,
        last_accrual_at TIMESTAMPTZ,
        total_reward_accrued NUMERIC(38,18) NOT NULL DEFAULT 0,
        total_reward_claimed NUMERIC(38,18) NOT NULL DEFAULT 0,
        version INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS public.staking_rewards (
        id VARCHAR(36) PRIMARY KEY,
        position_id VARCHAR(36) NOT NULL REFERENCES public.staking_positions(id) ON DELETE CASCADE,
        reward_type VARCHAR(16) NOT NULL,
        amount NUMERIC(38,18) NOT NULL,
        period_start TIMESTAMPTZ,
        period_end TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now())
    );

    CREATE TABLE IF NOT EXISTS public.staking_events (
        id VARCHAR(36) PRIMARY KEY,
        event_type VARCHAR(40) NOT NULL,
        user_telegram_id BIGINT NOT NULL,
        pool_id VARCHAR(36),
        position_id VARCHAR(36),
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc', now()),
        actor_type VARCHAR(16) NOT NULL DEFAULT 'SYSTEM',
        actor_id VARCHAR(64),
        amount NUMERIC(38,18)
    );
    """)


def downgrade():
    pass