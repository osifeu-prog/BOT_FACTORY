from __future__ import annotations

import os
import time

from fastapi import APIRouter, Header, HTTPException
from starlette.responses import JSONResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def _env(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None


def _require_admin_key(x_admin_key: str | None) -> None:
    expected = _env("ADMIN_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY not set")
    if not x_admin_key or x_admin_key.strip() != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


_last_call_ts: float = 0.0
_MIN_INTERVAL_SEC = 10.0


@router.post("/accrual/run")
def run_accrual(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """
    Run staking accrual once (admin-only).
    """
    global _last_call_ts
    _require_admin_key(x_admin_key)

    now = time.time()
    if now - _last_call_ts < _MIN_INTERVAL_SEC:
        raise HTTPException(status_code=429, detail="too_many_requests")
    _last_call_ts = now

    try:
        # local import to avoid impacting app startup
        from tools.run_staking_accrual_once import main as accrual_main  # type: ignore

        res = accrual_main()
        return JSONResponse({"ok": True, "ran": True, "result": res})
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
