"""baseline (db already exists)

Revision ID: 7cade31fdf8e
Revises: f72192edaf99
Create Date: 2026-01-01 16:45:28.339577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cade31fdf8e'
down_revision: Union[str, Sequence[str], None] = 'f72192edaf99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
