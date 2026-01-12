from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone

from app.db import get_db
from .service import accrue_position
from .schemas import AccrueResult, PositionsResponse, PositionOut

router = APIRouter(prefix="/staking", tags=["staking"])


@router.post("/accrue", response_model=list[AccrueResult])
def accrue_all(db: Session = Depends(get_db)):
    rows = db.execute(text("""
        select p.*, s.apy_bps
        from staking_positions p
        join staking_pools s on s.id = p.pool_id
        where p.state = 'ACTIVE'
    """)).mappings().all()

    now = datetime.now(timezone.utc)
    results = []

    for r in rows:
        reward = accrue_position(
            db,
            type("P", (), r),
            type("S", (), {"apy_bps": r["apy_bps"]}),
            now=now,
        )
        if reward > 0:
            results.append(
                AccrueResult(position_id=r["id"], reward=reward)
            )

    return results


@router.get("/positions/{telegram_id}", response_model=PositionsResponse)
def list_positions(telegram_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        select id, pool_id, principal_amount, state,
               activated_at, last_accrual_at, total_reward_accrued
        from staking_positions
        where user_telegram_id = :uid
        order by created_at desc
    """), {"uid": telegram_id}).mappings().all()

    return PositionsResponse(
        telegram_id=telegram_id,
        positions=[PositionOut(**r) for r in rows],
    )
