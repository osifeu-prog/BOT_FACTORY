import os
from sqlalchemy import create_engine, text

def main():
    e = create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        print("=== POOLS ===")
        pools = c.execute(text("""
            SELECT id, name, apy_bps, is_active, start_at, end_at, created_at
            FROM staking_pools
            ORDER BY created_at DESC
            LIMIT 5
        """)).mappings().all()
        for p in pools:
            print(dict(p))

        print("\n=== POSITIONS BY STATE ===")
        for r in c.execute(text("""
            SELECT state, COUNT(*) AS cnt
            FROM staking_positions
            GROUP BY state
            ORDER BY state
        """)).all():
            print(r)

        print("\n=== ACTIVE WITHOUT activated_at ===")
        rows = c.execute(text("""
            SELECT id, user_telegram_id, pool_id, state,
                   created_at, activated_at, last_accrual_at
            FROM staking_positions
            WHERE state='ACTIVE' AND activated_at IS NULL
            ORDER BY created_at DESC
        """)).mappings().all()
        for r in rows:
            print(dict(r))

if __name__ == "__main__":
    main()