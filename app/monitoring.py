import os
from typing import Any, Dict, List

from sqlalchemy import text

from app.core.config import settings
from app.database import SessionLocal
from app import blockchain


def _is_truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


def _check_database(checks: Dict[str, Any]) -> str:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        checks["database"] = {"ok": True}
        return "ok"
    except Exception as e:
        checks["database"] = {"ok": False, "error": str(e)}
        return "degraded"


def _check_env(checks: Dict[str, Any]) -> str:
    # ×—×©×•×‘: /ready ×œ×گ ×گ×‍×•×¨ ×œ×”×™×›×©×œ ×›×©×‍×¨×™×¦×™×‌ API-only (DISABLE_TELEGRAM_BOT=1)
    missing: List[str] = []

    disable_bot = _is_truthy(os.getenv("DISABLE_TELEGRAM_BOT") or "")
    bsc_rpc = (os.getenv("BSC_RPC_URL") or "").strip()

    required: List[str] = []

    # BOT_TOKEN × ×“×¨×© ×¨×§ ×گ×‌ ×”×‘×•×ک ×‍×•×¤×¢×œ
    if not disable_bot:
        required.append("BOT_TOKEN")

    # ×‍×©×ھ× ×™ BSC × ×“×¨×©×™×‌ ×¨×§ ×گ×‌ ×‘×™×§×©×ھ ×‘×›×œ×œ ×œ×‘×¦×¢ ×‘×“×™×§×•×ھ ×گ×•×ں-×¦'×™×™×ں
    if bsc_rpc:
        required.extend(["COMMUNITY_WALLET_ADDRESS", "SLH_TOKEN_ADDRESS"])

    for name in required:
        if not (os.getenv(name) or "").strip():
            missing.append(name)

    checks["env"] = {"ok": len(missing) == 0, "missing": missing}
    return "ok" if not missing else "degraded"


def _check_telegram(checks: Dict[str, Any], quick: bool) -> str:
    disable_bot = _is_truthy(os.getenv("DISABLE_TELEGRAM_BOT") or "")
    if disable_bot:
        checks["telegram"] = {"ok": True, "skipped": True, "reason": "DISABLE_TELEGRAM_BOT=1"}
        return "ok"

    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        checks["telegram"] = {"ok": False, "error": "BOT_TOKEN not configured"}
        return "degraded"

    # ×گ×‌ ×ھ×¨×¦×” later: ×‘×“×™×§×ھ getMe ×گ×‍×™×ھ×™×ھ. ×›×¨×’×¢ × ×©×‍×•×¨ ×™×¦×™×‘/×‍×”×™×¨.
    checks["telegram"] = {"ok": True}
    return "ok"


def _check_bsc(checks: Dict[str, Any]) -> str:
    bsc_rpc = (os.getenv("BSC_RPC_URL") or "").strip()
    if not bsc_rpc or not (settings.COMMUNITY_WALLET_ADDRESS or "").strip():
        checks["bsc"] = {"ok": True, "skipped": True, "reason": "BSC_RPC_URL or COMMUNITY_WALLET_ADDRESS missing"}
        return "ok"

    try:
        on = blockchain.get_onchain_balances(settings.COMMUNITY_WALLET_ADDRESS)
        checks["bsc"] = {"ok": True, "balances": on}
        return "ok"
    except Exception as e:
        checks["bsc"] = {"ok": False, "error": str(e)}
        return "degraded"


def run_checks(quick: bool = True) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    statuses = [
        _check_database(checks),
        _check_env(checks),
        _check_telegram(checks, quick=quick),
        _check_bsc(checks),
    ]
    overall = "ok" if all(s == "ok" for s in statuses) else "degraded"
    return {"status": overall, "checks": checks}

def run_selftest(quick: bool = True) -> Dict[str, Any]:
    # Backward-compatible alias (older main.py imports run_selftest)
    return run_checks(quick=quick)