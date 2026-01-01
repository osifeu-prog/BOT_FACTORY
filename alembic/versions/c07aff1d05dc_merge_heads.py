"""merge heads

Revision ID: c07aff1d05dc
Revises: 7cade31fdf8e, 20260101184108
Create Date: 2026-01-01 19:00:45.171653

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa



revision = 'c07aff1d05dc'
down_revision = ('7cade31fdf8e', '20260101184108')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass