"""
Single import point for Alembic + app startup.

Do NOT put legacy / mismatched schemas here.
Only import the modules that reflect the actual DB schema.
"""

from app.models_core import User, Account, LedgerEntry  # noqa: F401
from app.models_staking import StakingPool, StakingPosition, StakingReward, StakingEvent  # noqa: F401
from app.models_telegram import TelegramUpdate  # noqa: F401