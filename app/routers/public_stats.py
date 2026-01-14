from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from sqlalchemy import create_engine, text

router = APIRouter(tags=["public"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pick_db_url() -> str:
    # Railway: internal DATABASE_URL (postgres.railway.internal)
    return (os.getenv("DATABASE_URL") or "").strip()


def q1(engine, sql: str, params: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    with engine.begin() as c:
        r = c.execute(text(sql), params or {}).mappings().first()
        return dict(r) if r else None


@router.get("/stats")
def stats():
    """
    Public, read-only, safe stats for landing/bot.
    Never returns secrets. If DB missing/unreachable, returns partial info.
    """
    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_SHA")
    out: dict[str, Any] = {
        "ok": True,
        "ts": utcnow().isoformat(),
        "service": os.getenv("RAILWAY_SERVICE_NAME") or "BOT_FACTORY",
        "env": os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_ENVIRONMENT_NAME"),
        "git_sha": sha,
        "db": {"connected": False},
        "staking": {},
    }

    db_url = pick_db_url()
    if not db_url:
        out["db"]["reason"] = "DATABASE_URL_missing"
        return out

    try:
        e = create_engine(db_url, pool_pre_ping=True)

        ping = q1(e, "select 1 as ok")
        if not ping:
            out["db"]["reason"] = "ping_failed"
            return out

        out["db"]["connected"] = True

        counts = q1(
            e,
            """
            select
              (select count(*) from staking_pools) as pools,
              (select count(*) from staking_positions) as positions_total,
              (select count(*) from staking_positions where state='ACTIVE') as positions_active,
              (select count(*) from staking_rewards) as rewards_rows,
              (select count(*) from staking_events) as events_rows
            """,
        ) or {}

        last = q1(
            e,
            """
            select
              (select max(created_at) from staking_rewards) as last_reward_at,
              (select max(occurred_at) from staking_events) as last_event_at,
              (select max(last_accrual_at) from staking_positions) as last_accrual_at
            """,
        ) or {}

        tvl = q1(
            e,
            """
            select coalesce(sum(principal_amount),0)::text as tvl_principal
            from staking_positions
            where state='ACTIVE'
            """,
        ) or {}

        out["staking"] = {**counts, **last, **tvl}
        return out

    except Exception as ex:
        out["db"]["error"] = str(ex)
        return out
