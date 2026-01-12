import os
from sqlalchemy import create_engine, text

def main():
    e = create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        active = c.execute(text("SELECT COUNT(*) FROM staking_positions WHERE state = 'ACTIVE'")).scalar()
        rewards = c.execute(text("SELECT COUNT(*) FROM staking_rewards")).scalar()
        events  = c.execute(text("SELECT COUNT(*) FROM staking_events")).scalar()

        print("ACTIVE positions:", active)
        print("rewards:", rewards)
        print("events:", events)

        rows = c.execute(text("""
            SELECT id, user_telegram_id, pool_id, principal_amount, state,
                   activated_at, last_accrual_at
            FROM staking_positions
            ORDER BY created_at DESC
            LIMIT 10
        """)).mappings().all()

        print("\nLAST 10 positions:")
        for r in rows:
            print(dict(r))

if __name__ == "__main__":
    main()