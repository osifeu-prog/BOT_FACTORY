import os
from sqlalchemy import create_engine, text

SQL = """
UPDATE staking_positions
SET
  activated_at    = COALESCE(activated_at, created_at),
  last_accrual_at = COALESCE(last_accrual_at, COALESCE(activated_at, created_at))
WHERE state = 'ACTIVE'
  AND (activated_at IS NULL OR last_accrual_at IS NULL)
RETURNING id, user_telegram_id, state, created_at, activated_at, last_accrual_at
"""

def main():
    e = create_engine(os.environ["DATABASE_URL"])
    with e.begin() as c:
        rows = c.execute(text(SQL)).mappings().all()

    print("UPDATED:", len(rows))
    for r in rows:
        print(dict(r))

if __name__ == "__main__":
    main()