from __future__ import annotations

from decimal import Decimal

from app.database import SessionLocal
from app.models_staking import StakingPool


def main() -> None:
    db = SessionLocal()
    try:
        code = "SLH-30D"
        pool = db.query(StakingPool).filter(StakingPool.code == code).first()

        if not pool:
            pool = StakingPool(
                code=code,
                name="SLH 30D Fixed",
                description="Phase-1 test pool",
                asset_symbol="SLH",
                reward_asset_symbol="SLH",
                apy_bps=1200,  # 12.00%
                lock_seconds=30 * 24 * 60 * 60,  # 30 days
                early_withdraw_penalty_bps=500,  # 5.00%
                min_stake=Decimal("1"),
                max_stake=Decimal("1000000"),
                is_active=True,
                starts_at=None,
                ends_at=None,
            )
            db.add(pool)
            db.commit()
            db.refresh(pool)
            print("Created pool:", pool.code, pool.id)
        else:
            print("Pool exists:", pool.code, pool.id)
    finally:
        db.close()


if __name__ == "__main__":
    main()