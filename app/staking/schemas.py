from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


class AccrueResult(BaseModel):
    position_id: str
    reward: Decimal


class PositionOut(BaseModel):
    id: str
    pool_id: str
    principal_amount: Decimal
    state: str
    activated_at: Optional[datetime]
    last_accrual_at: Optional[datetime]
    total_reward_accrued: Decimal


class PositionsResponse(BaseModel):
    telegram_id: int
    positions: List[PositionOut]
