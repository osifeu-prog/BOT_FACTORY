from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, getcontext

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

getcontext().prec = 50

SECONDS_PER_YEAR = Decimal("31536000")  # 365 days

LOCK_ID = 912345678

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def quant18(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.000000000000000001"), rounding=ROUND_DOWN)

def pick_db_url() -> str:
    """
    Prefer DATABASE_URL, but if it's a Railway internal hostname (postgres.railway.internal)
    and we're running locally, fallback to DATABASE_PUBLIC_URL when available.
    """
    url = (os.getenv("DATABASE_URL") or "").strip()
    pub = (os.getenv("DATABASE_PUBLIC_URL") or "").strip()

    if not url and pub:
        return pub

    if "railway.internal" in url.lower() and pub:
        return pub

    if not url:
        raise SystemExit("DATABASE_URL is not set (and no DATABASE_PUBLIC_URL fallback found).")

    return url

def q1(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {}).mappings().first()

def qall(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {}).mappings().all()

def main():
    db_url = pick_db_url()
    e = create_engine(db_url)

    now = utcnow()

    with e.begin() as c:
        locked = q1(c, "SELECT pg_try_advisory_lock(:id) AS ok", {"id": LOCK_ID})["ok"]
        if not locked:
            print("Another accrual is running (advisory lock busy). Exiting.")
            return

        updated_positions = 0
        inserted_rewards = 0
        inserted_events = 0
        completed_positions = 0

        try:
            rows = qall(
                c,
                """
                SELECT
                    p.id              AS position_id,
                    p.user_telegram_id,
                    p.pool_id,
                    p.principal_amount,
                    p.state,
                    p.activated_at,
                    p.matures_at,
                    p.last_accrual_at,
                    p.total_reward_accrued,
                    p.total_reward_claimed,
                    p.version,
                    pool.apy_bps,
                    pool.ends_at AS pool_ends_at,
                    pool.starts_at AS pool_starts_at
                FROM staking_positions p
                JOIN staking_pools pool ON pool.id = p.pool_id
                WHERE p.state = 'ACTIVE'
                ORDER BY p.created_at ASC
                FOR UPDATE
                """
            )

            if not rows:
                print("No ACTIVE positions found.")
                return

            for r in rows:
                pos_id = r["position_id"]
                user_id = r["user_telegram_id"]
                pool_id = r["pool_id"]

                principal = Decimal(str(r["principal_amount"]))
                apy_bps = Decimal(str(r["apy_bps"]))
                apy = apy_bps / Decimal("10000")

                start_ts = r["last_accrual_at"] or r["activated_at"] or now

                end_ts = now
                if r["matures_at"] is not None and r["matures_at"] < end_ts:
                    end_ts = r["matures_at"]
                if r["pool_ends_at"] is not None and r["pool_ends_at"] < end_ts:
                    end_ts = r["pool_ends_at"]

                if end_ts <= start_ts:
                    continue

                delta_seconds = Decimal(str((end_ts - start_ts).total_seconds()))
                if delta_seconds <= 0:
                    continue

                reward = principal * apy * (delta_seconds / SECONDS_PER_YEAR)
                reward = quant18(reward)

                # Always advance last_accrual_at
                if reward <= 0:
                    c.execute(
                        text("""
                            UPDATE staking_positions
                            SET last_accrual_at = :end_ts,
                                version = version + 1
                            WHERE id = :pid
                        """),
                        {"end_ts": end_ts, "pid": pos_id},
                    )
                    updated_positions += 1
                    continue

                total_accrued = Decimal(str(r["total_reward_accrued"] or 0))
                new_total_accrued = total_accrued + reward

                c.execute(
                    text("""
                        UPDATE staking_positions
                        SET last_accrual_at = :end_ts,
                            total_reward_accrued = :new_total,
                            version = version + 1
                        WHERE id = :pid
                    """),
                    {"end_ts": end_ts, "new_total": new_total_accrued, "pid": pos_id},
                )
                updated_positions += 1

                reward_id = str(uuid.uuid4())
                c.execute(
                    text("""
                        INSERT INTO staking_rewards (
                            id, position_id, reward_type, amount,
                            period_start, period_end, created_at
                        ) VALUES (
                            :id, :position_id, :reward_type, :amount,
                            :period_start, :period_end, :created_at
                        )
                    """),
                    {
                        "id": reward_id,
                        "position_id": pos_id,
                        "reward_type": "ACCRUAL",
                        "amount": reward,
                        "period_start": start_ts,
                        "period_end": end_ts,
                        "created_at": now,
                    },
                )
                inserted_rewards += 1

                event_id = str(uuid.uuid4())
                details = {
                    "reward_id": reward_id,
                    "amount": str(reward),
                    "from": start_ts.isoformat(),
                    "to": end_ts.isoformat(),
                }

                c.execute(
                    text("""
                        INSERT INTO staking_events (
                            id, event_type, user_telegram_id, pool_id, position_id,
                            occurred_at, details
                        ) VALUES (
                            :id, :event_type, :user_telegram_id, :pool_id, :position_id,
                            :occurred_at, :details
                        )
                    """).bindparams(bindparam("details", type_=JSONB)),
                    {
                        "id": event_id,
                        "event_type": "REWARD_ACCRUED",
                        "user_telegram_id": user_id,
                        "pool_id": pool_id,
                        "position_id": pos_id,
                        "occurred_at": now,
                        "details": details,
                    },
                )
                inserted_events += 1

                if r["matures_at"] is not None and now >= r["matures_at"]:
                    c.execute(
                        text("""
                            UPDATE staking_positions
                            SET state = 'COMPLETED',
                                closed_at = COALESCE(closed_at, :closed_at),
                                version = version + 1
                            WHERE id = :pid AND state = 'ACTIVE'
                        """),
                        {"closed_at": now, "pid": pos_id},
                    )
                    completed_positions += 1

                    event_id2 = str(uuid.uuid4())
                    c.execute(
                        text("""
                            INSERT INTO staking_events (
                                id, event_type, user_telegram_id, pool_id, position_id,
                                occurred_at, details
                            ) VALUES (
                                :id, :event_type, :user_telegram_id, :pool_id, :position_id,
                                :occurred_at, :details
                            )
                        """).bindparams(bindparam("details", type_=JSONB)),
                        {
                            "id": event_id2,
                            "event_type": "POSITION_COMPLETED",
                            "user_telegram_id": user_id,
                            "pool_id": pool_id,
                            "position_id": pos_id,
                            "occurred_at": now,
                            "details": {"reason": "matured"},
                        },
                    )
                    inserted_events += 1

            print("ACCRUAL DONE")
            print("updated_positions:", updated_positions)
            print("inserted_rewards:", inserted_rewards)
            print("inserted_events:", inserted_events)
            print("completed_positions:", completed_positions)

        finally:
            # release lock best-effort
            try:
                c.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            except Exception:
                pass

if __name__ == "__main__":
    main()
