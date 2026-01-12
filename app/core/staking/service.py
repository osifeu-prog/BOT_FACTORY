from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.staking.calculator import calc_reward
from app.core.staking.state import assert_transition
from app.models_staking import (
    StakingActorType,
    StakingEvent,
    StakingEventType,
    StakingPool,
    StakingPosition,
    StakingPositionState,
    StakingReward,
    StakingRewardType,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _d(x: Decimal | int | str) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _q18(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.000000000000000001"))


def list_active_pools(db: Session) -> list[StakingPool]:
    return db.query(StakingPool).filter(StakingPool.is_active.is_(True)).order_by(StakingPool.code.asc()).all()


def get_pool_by_code(db: Session, code: str) -> StakingPool | None:
    return db.query(StakingPool).filter(StakingPool.code == code).first()


def get_position_for_update(db: Session, position_id: str) -> StakingPosition:
    pos = (
        db.query(StakingPosition)
        .filter(StakingPosition.id == position_id)
        .with_for_update()
        .first()
    )
    if not pos:
        raise ValueError("Position not found")
    return pos


def create_and_activate_position(
    db: Session,
    telegram_id: int,
    pool: StakingPool,
    amount: Decimal,
    actor_type: str = StakingActorType.USER.value,
    actor_id: str | None = None,
) -> StakingPosition:
    amt = _d(amount)
    if amt <= 0:
        raise ValueError("Amount must be > 0")

    if pool.min_stake is not None and amt < _d(pool.min_stake):
        raise ValueError("Amount below pool minimum")
    if pool.max_stake is not None and amt > _d(pool.max_stake):
        raise ValueError("Amount above pool maximum")
    if not pool.is_active:
        raise ValueError("Pool is not active")

    pos = StakingPosition(
        user_telegram_id=int(telegram_id),
        pool_id=pool.id,
        principal_amount=_q18(amt),
        state=StakingPositionState.CREATED.value,
        total_reward_accrued=_q18(Decimal("0")),
        total_reward_claimed=_q18(Decimal("0")),
        version=1,
    )
    db.add(pos)
    db.flush()

    db.add(
        StakingEvent(
            event_type=StakingEventType.POSITION_CREATED.value,
            user_telegram_id=int(telegram_id),
            pool_id=pool.id,
            position_id=pos.id,
            actor_type=actor_type,
            actor_id=actor_id,
            amount=_q18(amt),
            details={"pool_code": pool.code},
        )
    )

    # Activate immediately (Phase 1)
    now = utcnow()
    assert_transition(pos.state, StakingPositionState.ACTIVE.value)
    pos.state = StakingPositionState.ACTIVE.value
    pos.activated_at = now
    pos.last_accrual_at = now
    if pool.lock_seconds and pool.lock_seconds > 0:
        pos.matures_at = datetime.fromtimestamp(now.timestamp() + int(pool.lock_seconds), tz=timezone.utc)

    db.add(
        StakingEvent(
            event_type=StakingEventType.POSITION_ACTIVATED.value,
            user_telegram_id=int(telegram_id),
            pool_id=pool.id,
            position_id=pos.id,
            actor_type=StakingActorType.SYSTEM.value,
            actor_id=None,
            details={"activated_at": now.isoformat()},
        )
    )

    db.flush()
    return pos


def accrue_position(db: Session, pos: StakingPosition, now: datetime | None = None) -> Decimal:
    now = now or utcnow()

    if pos.state not in (StakingPositionState.ACTIVE.value, StakingPositionState.COMPLETED.value):
        return _q18(Decimal("0"))

    pool = db.query(StakingPool).filter(StakingPool.id == pos.pool_id).first()
    if not pool:
        raise ValueError("Pool not found for position")

    start = pos.last_accrual_at or pos.activated_at or pos.created_at
    end = now

    # do not accrue beyond maturity if matured and not yet marked completed
    if pos.matures_at is not None and end > pos.matures_at:
        end = pos.matures_at

    if end <= start:
        return _q18(Decimal("0"))

    res = calc_reward(_d(pos.principal_amount), int(pool.apy_bps), start, end)
    if res.amount <= 0:
        pos.last_accrual_at = end
        pos.version += 1
        db.flush()
        return _q18(Decimal("0"))

    reward = _q18(res.amount)

    db.add(
        StakingReward(
            position_id=pos.id,
            reward_type=StakingRewardType.ACCRUAL.value,
            amount=reward,
            period_start=start,
            period_end=end,
            meta={
                "apy_bps": int(pool.apy_bps),
                "seconds": res.seconds,
                "method": "continuous_seconds_365d",
                "pool_code": pool.code,
            },
        )
    )

    pos.total_reward_accrued = _q18(_d(pos.total_reward_accrued) + reward)
    pos.last_accrual_at = end
    pos.version += 1

    db.add(
        StakingEvent(
            event_type=StakingEventType.ACCRUAL_RECORDED.value,
            user_telegram_id=int(pos.user_telegram_id),
            pool_id=pool.id,
            position_id=pos.id,
            actor_type=StakingActorType.SYSTEM.value,
            amount=reward,
            details={"period_start": start.isoformat(), "period_end": end.isoformat(), "pool_code": pool.code},
        )
    )

    # If matured, mark completed (non-destructive)
    if pos.matures_at is not None and now >= pos.matures_at and pos.state == StakingPositionState.ACTIVE.value:
        assert_transition(pos.state, StakingPositionState.COMPLETED.value)
        pos.state = StakingPositionState.COMPLETED.value
        pos.version += 1
        db.add(
            StakingEvent(
                event_type=StakingEventType.POSITION_COMPLETED.value,
                user_telegram_id=int(pos.user_telegram_id),
                pool_id=pool.id,
                position_id=pos.id,
                actor_type=StakingActorType.SYSTEM.value,
                details={"matures_at": pos.matures_at.isoformat()},
            )
        )

    db.flush()
    return reward


def compute_claimable(pos: StakingPosition) -> Decimal:
    claimable = _d(pos.total_reward_accrued) - _d(pos.total_reward_claimed)
    if claimable <= 0:
        return _q18(Decimal("0"))
    return _q18(claimable)


def claim_rewards(
    db: Session,
    position_id: str,
    telegram_id: int,
    request_id: str | None = None,
) -> Decimal:
    pos = get_position_for_update(db, position_id)
    if int(pos.user_telegram_id) != int(telegram_id):
        raise PermissionError("Not your position")

    accrue_position(db, pos, utcnow())
    claimable = compute_claimable(pos)
    if claimable <= 0:
        return _q18(Decimal("0"))

    rid = request_id or str(uuid.uuid4())

    # idempotency: if request_id already exists, no double-claim
    exists = db.query(StakingEvent).filter(StakingEvent.request_id == rid).first()
    if exists:
        return _q18(Decimal("0"))

    db.add(
        StakingReward(
            position_id=pos.id,
            reward_type=StakingRewardType.CLAIM.value,
            amount=claimable,
            period_start=None,
            period_end=None,
            meta={"request_id": rid},
        )
    )

    pos.total_reward_claimed = _q18(_d(pos.total_reward_claimed) + claimable)
    pos.version += 1

    db.add(
        StakingEvent(
            event_type=StakingEventType.REWARD_CLAIMED.value,
            user_telegram_id=int(pos.user_telegram_id),
            pool_id=pos.pool_id,
            position_id=pos.id,
            request_id=rid,
            actor_type=StakingActorType.USER.value,
            actor_id=str(telegram_id),
            amount=claimable,
            details={},
        )
    )

    db.flush()
    return claimable


def prepare_unstake_quote(db: Session, position_id: str, telegram_id: int) -> dict:
    pos = get_position_for_update(db, position_id)
    if int(pos.user_telegram_id) != int(telegram_id):
        raise PermissionError("Not your position")

    pool = db.query(StakingPool).filter(StakingPool.id == pos.pool_id).first()
    if not pool:
        raise ValueError("Pool not found")

    now = utcnow()
    accrue_position(db, pos, now)
    claimable = compute_claimable(pos)

    penalty = Decimal("0")
    matured = (pos.matures_at is None) or (now >= pos.matures_at)
    if (not matured) and pool.early_withdraw_penalty_bps and pool.early_withdraw_penalty_bps > 0:
        penalty = _q18(_d(pos.principal_amount) * (Decimal(int(pool.early_withdraw_penalty_bps)) / Decimal(10000)))

    net_principal = _q18(_d(pos.principal_amount) - penalty)

    return {
        "position_id": pos.id,
        "pool_code": pool.code,
        "state": pos.state,
        "principal": str(_q18(_d(pos.principal_amount))),
        "claimable_reward": str(claimable),
        "penalty": str(penalty),
        "net_principal": str(net_principal),
        "matures_at": pos.matures_at.isoformat() if pos.matures_at else None,
        "matured": matured,
    }


def confirm_unstake(
    db: Session,
    position_id: str,
    telegram_id: int,
    request_id: str,
) -> dict:
    if not request_id:
        raise ValueError("request_id required")

    pos = get_position_for_update(db, position_id)
    if int(pos.user_telegram_id) != int(telegram_id):
        raise PermissionError("Not your position")

    # idempotency
    exists = db.query(StakingEvent).filter(StakingEvent.request_id == request_id).first()
    if exists:
        return {"ok": True, "idempotent": True}

    pool = db.query(StakingPool).filter(StakingPool.id == pos.pool_id).first()
    if not pool:
        raise ValueError("Pool not found")

    now = utcnow()
    accrue_position(db, pos, now)

    db.add(
        StakingEvent(
            event_type=StakingEventType.UNSTAKE_REQUESTED.value,
            user_telegram_id=int(pos.user_telegram_id),
            pool_id=pool.id,
            position_id=pos.id,
            request_id=request_id,
            actor_type=StakingActorType.USER.value,
            actor_id=str(telegram_id),
            details={},
        )
    )

    matured = (pos.matures_at is None) or (now >= pos.matures_at)

    penalty = Decimal("0")
    if (not matured) and pool.early_withdraw_penalty_bps and pool.early_withdraw_penalty_bps > 0:
        penalty = _q18(_d(pos.principal_amount) * (Decimal(int(pool.early_withdraw_penalty_bps)) / Decimal(10000)))

    # Transition to WITHDRAWN
    if pos.state in (StakingPositionState.CREATED.value,):
        assert_transition(pos.state, StakingPositionState.CANCELLED.value)
        pos.state = StakingPositionState.CANCELLED.value
        pos.closed_at = now
    else:
        assert_transition(pos.state, StakingPositionState.WITHDRAWN.value)
        pos.state = StakingPositionState.WITHDRAWN.value
        pos.closed_at = now

    pos.version += 1

    db.add(
        StakingEvent(
            event_type=StakingEventType.POSITION_WITHDRAWN.value,
            user_telegram_id=int(pos.user_telegram_id),
            pool_id=pool.id,
            position_id=pos.id,
            request_id=str(uuid.uuid4()),
            actor_type=StakingActorType.SYSTEM.value,
            amount=_q18(_d(pos.principal_amount)),
            details={"penalty": str(penalty), "matured": matured},
        )
    )

    db.flush()
    return {"ok": True, "penalty": str(penalty), "matured": matured}
def accrue_all_active_positions(db: Session, now: datetime | None = None) -> list[dict]:
    """
    Deterministic accrual for all ACTIVE positions.
    Returns list of {position_id, reward} for rewards > 0.
    """
    now = now or datetime.now(timezone.utc)

    rows = db.execute(text("""
        select p.id, p.user_telegram_id, p.pool_id, p.principal_amount,
               p.state, p.activated_at, p.last_accrual_at, p.total_reward_accrued,
               s.apy_bps
        from staking_positions p
        join staking_pools s on s.id = p.pool_id
        where p.state = 'ACTIVE'
    """)).mappings().all()

    results: list[dict] = []

    for r in rows:
        # last accrual point
        last = r["last_accrual_at"] or r["activated_at"]
        if not last:
            continue

        elapsed = int((now - last).total_seconds())
        if elapsed <= 0:
            continue

        # linear reward
        rate = float(r["apy_bps"]) / 10_000.0
        reward = (float(r["principal_amount"]) * rate) * (elapsed / (365.0 * 24.0 * 60.0 * 60.0))
        if reward <= 0:
            continue

        # persist
        db.execute(text("""
            update staking_positions
            set last_accrual_at = :now,
                total_reward_accrued = total_reward_accrued + :reward
            where id = :id
        """), {"now": now, "reward": reward, "id": r["id"]})

        db.execute(text("""
            insert into staking_rewards
            (id, position_id, reward_type, amount, period_start, period_end)
            values
            (gen_random_uuid(), :pid, 'ACCRUAL', :amt, :start, :end)
        """), {"pid": r["id"], "amt": reward, "start": last, "end": now})

        db.execute(text("""
            insert into staking_events
            (id, event_type, user_telegram_id, pool_id, position_id, details)
            values
            (gen_random_uuid(), 'ACCRUAL', :uid, :pool, :pid, :details::jsonb)
        """), {
            "uid": r["user_telegram_id"],
            "pool": r["pool_id"],
            "pid": r["id"],
            "details": '{"elapsed_seconds": ' + str(elapsed) + ', "apy_bps": ' + str(r["apy_bps"]) + ', "reward": "' + str(reward) + '"}'
        })

        results.append({"position_id": r["id"], "reward": str(reward)})

    return results