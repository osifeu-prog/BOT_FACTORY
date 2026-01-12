from decimal import Decimal
from .constants import YEAR_SECONDS, ZERO

def calculate_reward(
    principal: Decimal,
    apy_bps: int,
    elapsed_seconds: int,
) -> Decimal:
    if elapsed_seconds <= 0 or apy_bps <= 0:
        return ZERO

    rate = Decimal(apy_bps) / Decimal(10_000)
    return principal * rate * (Decimal(elapsed_seconds) / YEAR_SECONDS)
