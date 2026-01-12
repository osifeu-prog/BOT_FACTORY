from datetime import datetime, timezone
from sqlalchemy import text

from .accrual import calculate_reward
from .constants import ZERO

def accrue_position(db, position, pool, now=None):
    if position.state != "ACTIVE":
        return ZERO

    now = now or datetime.now(timezone.utc)
    last = position.last_accrual_at or position.activated_at
    if not last:
        return ZERO

    elapsed = int((now - last).total_seconds())
    if elapsed <= 0:
        return ZERO

    reward = calculate_reward(
        position.principal_amount,
        pool.apy_bps,
        elapsed,
    )

    if reward <= ZERO:
        return ZERO

    position.last_accrual_at = now
    position.total_reward_accrued += reward
    db.add(position)

    db.execute(text("""
        insert into staking_rewards
        (id, position_id, reward_type, amount, period_start, period_end)
        values
        (gen_random_uuid(), :pid, 'ACCRUAL', :amt, :start, :end)
    """), {
        "pid": position.id,
        "amt": reward,
        "start": last,
        "end": now,
    })

    db.execute(text("""
        insert into staking_events
        (id, event_type, user_telegram_id, pool_id, position_id, details)
        values
        (gen_random_uuid(), 'ACCRUAL', :uid, :pool, :pid, :details)
    """), {
        "uid": position.user_telegram_id,
        "pool": position.pool_id,
        "pid": position.id,
        "details": {
            "elapsed_seconds": elapsed,
            "apy_bps": pool.apy_bps,
            "reward": str(reward),
        },
    })

    return reward
