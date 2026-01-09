from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PoolOut(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str] = None
    asset_symbol: str
    reward_asset_symbol: str
    apy_bps: int
    lock_seconds: int
    early_withdraw_penalty_bps: int
    min_stake: Optional[Decimal] = None
    max_stake: Optional[Decimal] = None
    is_active: bool
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class CreatePositionIn(BaseModel):
    telegram_id: int = Field(..., ge=1)
    pool_code: str = Field(..., min_length=1, max_length=64)
    amount: Decimal = Field(..., gt=0)


class PositionOut(BaseModel):
    id: str
    telegram_id: int
    pool_id: str
    principal_amount: Decimal
    state: str
    created_at: datetime
    activated_at: Optional[datetime] = None
    matures_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    last_accrual_at: Optional[datetime] = None
    total_reward_accrued: Decimal
    total_reward_claimed: Decimal


class ClaimIn(BaseModel):
    telegram_id: int = Field(..., ge=1)
    request_id: Optional[str] = None


class ClaimOut(BaseModel):
    position_id: str
    claimed: Decimal


class UnstakePrepareIn(BaseModel):
    telegram_id: int = Field(..., ge=1)


class UnstakePrepareOut(BaseModel):
    position_id: str
    pool_code: str
    state: str
    principal: str
    claimable_reward: str
    penalty: str
    net_principal: str
    matures_at: Optional[str] = None
    matured: bool


class UnstakeConfirmIn(BaseModel):
    telegram_id: int = Field(..., ge=1)
    request_id: str = Field(..., min_length=8, max_length=64)


class UnstakeConfirmOut(BaseModel):
    ok: bool
    penalty: str | None = None
    matured: bool | None = None
    idempotent: bool | None = None