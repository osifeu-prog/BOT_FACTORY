from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, getcontext

getcontext().prec = 60

SECONDS_IN_YEAR = Decimal(365 * 24 * 60 * 60)
Q18 = Decimal("0.000000000000000001")


@dataclass(frozen=True)
class RewardCalcResult:
    amount: Decimal
    seconds: int


def _quantize_18(x: Decimal) -> Decimal:
    if x <= 0:
        return Decimal("0").quantize(Q18)
    return x.quantize(Q18, rounding=ROUND_DOWN)


def calc_reward(principal: Decimal, apy_bps: int, start: datetime, end: datetime) -> RewardCalcResult:
    """
    Deterministic accrual:
    reward = principal * (apy_bps/10000) * (delta_seconds / seconds_in_year)
    - Uses constant 365d year for determinism.
    - Rounds DOWN to 18 decimals to avoid drift.
    """
    if end <= start:
        return RewardCalcResult(amount=Decimal("0").quantize(Q18), seconds=0)

    delta_seconds = int((end - start).total_seconds())
    if delta_seconds <= 0 or principal <= 0 or apy_bps <= 0:
        return RewardCalcResult(amount=Decimal("0").quantize(Q18), seconds=max(delta_seconds, 0))

    rate = (Decimal(apy_bps) / Decimal(10000))
    amount = Decimal(principal) * rate * (Decimal(delta_seconds) / SECONDS_IN_YEAR)
    return RewardCalcResult(amount=_quantize_18(amount), seconds=delta_seconds)