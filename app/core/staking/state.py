from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models_staking import StakingPositionState


class StakingStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    reason: str


ALLOWED = {
    (StakingPositionState.CREATED.value, StakingPositionState.ACTIVE.value),
    (StakingPositionState.ACTIVE.value, StakingPositionState.COMPLETED.value),
    (StakingPositionState.ACTIVE.value, StakingPositionState.WITHDRAWN.value),
    (StakingPositionState.CREATED.value, StakingPositionState.CANCELLED.value),
    (StakingPositionState.ACTIVE.value, StakingPositionState.CANCELLED.value),
    (StakingPositionState.COMPLETED.value, StakingPositionState.WITHDRAWN.value),
}


def assert_transition(from_state: str, to_state: str) -> None:
    if (from_state, to_state) not in ALLOWED:
        raise StakingStateError(f"Invalid transition: {from_state} -> {to_state}")


def can_withdraw(now: datetime, matures_at: datetime | None) -> bool:
    # Always allow withdrawal (penalty may apply). Lock logic enforced by service (penalty).
    return True