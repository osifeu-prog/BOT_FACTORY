import os
from sqlalchemy import create_engine, text

def q(conn, sql: str):
    return conn.execute(text(sql)).mappings().all()

def main():
    e = create_engine(os.environ["DATABASE_URL"])
    with e.connect() as c:
        print("=== staking_pools columns ===")
        cols = q(c, """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='staking_pools'
            ORDER BY ordinal_position
        """)
        pool_cols = [r["column_name"] for r in cols]
        print(pool_cols)

        # pick best candidates
        starts_col = "starts_at" if "starts_at" in pool_cols else ("start_at" if "start_at" in pool_cols else None)
        ends_col   = "ends_at"   if "ends_at"   in pool_cols else ("end_at"   if "end_at"   in pool_cols else None)

        select_cols = ["id", "name", "apy_bps", "is_active"]
        if starts_col: select_cols.append(starts_col)
        if ends_col:   select_cols.append(ends_col)
        select_cols.append("created_at")

        print("\n=== POOLS (last 5) ===")
        pools = q(c, f"""
            SELECT {", ".join(select_cols)}
            FROM staking_pools
            ORDER BY created_at DESC
            LIMIT 5
        """)
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
        rows = q(c, """
            SELECT id, user_telegram_id, pool_id, state,
                   created_at, activated_at, last_accrual_at
            FROM staking_positions
            WHERE state='ACTIVE' AND activated_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)
        for r in rows:
            print(dict(r))

if __name__ == "__main__":
    main()