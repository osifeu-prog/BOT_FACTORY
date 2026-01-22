"""create core financial tables v3

Revises: 46be64a69648
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "27a0485a5534"
down_revision = "46be64a69648"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE EXTENSION IF NOT EXISTS pgcrypto;

        CREATE TABLE IF NOT EXISTS public.users (
            id          BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username    TEXT,
            first_name  TEXT,
            last_name   TEXT,
            is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS public.accounts (
            id         BIGSERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            currency   TEXT NOT NULL DEFAULT 'USD',
            kind       TEXT NOT NULL DEFAULT 'MAIN',
            status     TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, currency, kind)
        );

        CREATE TABLE IF NOT EXISTS public.ledger_entries (
            id         BIGSERIAL PRIMARY KEY,
            account_id BIGINT NOT NULL REFERENCES public.accounts(id) ON DELETE RESTRICT,
            direction  TEXT NOT NULL CHECK (direction IN ('DEBIT','CREDIT')),
            amount     NUMERIC(38, 18) NOT NULL CHECK (amount >= 0),
            asset      TEXT NOT NULL DEFAULT 'USD',
            ref_type   TEXT,
            ref_id     TEXT,
            memo       TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_ledger_account_created_at
          ON public.ledger_entries (account_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS ix_users_telegram_id
          ON public.users (telegram_id);

        CREATE TABLE IF NOT EXISTS public.telegram_updates (
            id               BIGSERIAL PRIMARY KEY,
            update_id        BIGINT,
            telegram_user_id BIGINT,
            payload          JSONB,
            received_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS ix_telegram_updates_received_at
          ON public.telegram_updates (received_at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS public.telegram_updates;
        DROP TABLE IF EXISTS public.ledger_entries;
        DROP TABLE IF EXISTS public.accounts;
        DROP TABLE IF EXISTS public.users;
        """
    )