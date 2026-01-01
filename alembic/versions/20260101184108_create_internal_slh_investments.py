from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260101184108"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deposits",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_ils", sa.Numeric(18, 2), nullable=False),
        sa.Column("method", sa.String(32), nullable=False, server_default="bank"),
        sa.Column("reference", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_deposits_user_id", "deposits", ["user_id"])

    op.create_table(
        "slh_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_slh", sa.Numeric(28, 8), nullable=False),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("ref_type", sa.String(32), nullable=True),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_slh_ledger_user_id", "slh_ledger", ["user_id"])
    op.create_index("ix_slh_ledger_ref", "slh_ledger", ["ref_type", "ref_id"])

    op.create_table(
        "redemption_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slh_amount", sa.Numeric(28, 8), nullable=False),
        sa.Column("target", sa.String(256), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="requested"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_admin", sa.Integer(), nullable=True),
    )
    op.create_index("ix_redemption_requests_user_id", "redemption_requests", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_redemption_requests_user_id", table_name="redemption_requests")
    op.drop_table("redemption_requests")

    op.drop_index("ix_slh_ledger_ref", table_name="slh_ledger")
    op.drop_index("ix_slh_ledger_user_id", table_name="slh_ledger")
    op.drop_table("slh_ledger")

    op.drop_index("ix_deposits_user_id", table_name="deposits")
    op.drop_table("deposits")