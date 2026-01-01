from __future__ import annotations

# Marker revision to attach the investments branch onto the existing Alembic chain.
# Must not modify schema because DB already exists in production.

revision = "20260101184108"
down_revision = "7cade31fdf8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass