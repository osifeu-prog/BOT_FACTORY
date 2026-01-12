from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import text
from app.staking.service import accrue_position

from app.database import get_db
from app.models_staking import StakingPool, StakingPosition
from app.core.staking import service
from app.schemas_staking import (
    PoolOut,
    CreatePositionIn,
    PositionOut,
    ClaimIn,
    ClaimOut,
    UnstakePrepareIn,
    UnstakePrepareOut,
    UnstakeConfirmIn,
    UnstakeConfirmOut,
)

router = APIRouter(prefix="/staking", tags=["staking"])


def _pool_out(p: StakingPool) -> PoolOut:
    return PoolOut(
        id=p.id,
        code=p.code,
        name=p.name,
        description=p.description,
        asset_symbol=p.asset_symbol,
        reward_asset_symbol=p.reward_asset_symbol,
        apy_bps=p.apy_bps,
        lock_seconds=p.lock_seconds,
        early_withdraw_penalty_bps=p.early_withdraw_penalty_bps,
        min_stake=p.min_stake,
        max_stake=p.max_stake,
        is_active=p.is_active,
        starts_at=p.starts_at,
        ends_at=p.ends_at,
    )


def _pos_out(pos: StakingPosition) -> PositionOut:
    return PositionOut(
        id=pos.id,
        telegram_id=int(pos.user_telegram_id),
        pool_id=pos.pool_id,
        principal_amount=pos.principal_amount,
        state=pos.state,
        created_at=pos.created_at,
        activated_at=pos.activated_at,
        matures_at=pos.matures_at,
        closed_at=pos.closed_at,
        last_accrual_at=pos.last_accrual_at,
        total_reward_accrued=pos.total_reward_accrued,
        total_reward_claimed=pos.total_reward_claimed,
    )


@router.get("/pools", response_model=list[PoolOut])
def list_pools(db: Session = Depends(get_db)):
    pools = service.list_active_pools(db)
    return [_pool_out(p) for p in pools]


@router.get("/pools/{code}", response_model=PoolOut)
def get_pool(code: str, db: Session = Depends(get_db)):
    pool = service.get_pool_by_code(db, code)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return _pool_out(pool)


@router.post("/positions", response_model=PositionOut)
def create_position(body: CreatePositionIn, db: Session = Depends(get_db)):
    pool = service.get_pool_by_code(db, body.pool_code)
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    try:
        pos = service.create_and_activate_position(db, body.telegram_id, pool, body.amount)
        db.commit()
        db.refresh(pos)
        return _pos_out(pos)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ---- Accrual (admin / internal) ----
@router.post("/accrue")
def accrue_all(db: Session = Depends(get_db)):
    """
    Accrue rewards for all ACTIVE positions (deterministic).
    Returns list of {position_id, reward} for rewards > 0.
    """
    try:
        results = service.accrue_all_active_positions(db)
        db.commit()
        return results
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/positions", response_model=list[PositionOut])
def list_positions(telegram_id: int, db: Session = Depends(get_db)):
    positions = (
        db.query(StakingPosition)
        .filter(StakingPosition.user_telegram_id == int(telegram_id))
        .order_by(StakingPosition.created_at.desc())
        .all()
    )
    return [_pos_out(p) for p in positions]


@router.get("/positions/{position_id}", response_model=PositionOut)
def get_position(position_id: str, db: Session = Depends(get_db)):
    pos = db.query(StakingPosition).filter(StakingPosition.id == position_id).first()
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found")
    return _pos_out(pos)


@router.post("/positions/{position_id}/claim", response_model=ClaimOut)
def claim(position_id: str, body: ClaimIn, db: Session = Depends(get_db)):
    try:
        claimed = service.claim_rewards(db, position_id, body.telegram_id, body.request_id)
        db.commit()
        return ClaimOut(position_id=position_id, claimed=claimed)
    except PermissionError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/positions/{position_id}/unstake/prepare", response_model=UnstakePrepareOut)
def unstake_prepare(position_id: str, body: UnstakePrepareIn, db: Session = Depends(get_db)):
    try:
        quote = service.prepare_unstake_quote(db, position_id, body.telegram_id)
        db.commit()
        return UnstakePrepareOut(**quote)
    except PermissionError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/positions/{position_id}/unstake/confirm", response_model=UnstakeConfirmOut)
def unstake_confirm(position_id: str, body: UnstakeConfirmIn, db: Session = Depends(get_db)):
    try:
        out = service.confirm_unstake(db, position_id, body.telegram_id, body.request_id)
        db.commit()
        return UnstakeConfirmOut(**out)
    except PermissionError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
