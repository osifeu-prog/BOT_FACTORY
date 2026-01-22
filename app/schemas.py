from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------- Users ----------

class UserUpsertIn(_Base):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserOut(_Base):
    id: int
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_admin: bool


# ---------- Accounts / Ledger ----------

class LedgerCreditIn(_Base):
    telegram_id: int
    currency: str = "USD"
    kind: str = "MAIN"
    amount: str = Field(..., description="Decimal string, e.g. '10.50'")
    memo: Optional[str] = None
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None


class LedgerPostResult(_Base):
    ok: bool
    ledger_id: int
    account_id: int


class BalanceOut(_Base):
    telegram_id: int
    account_id: int
    currency: str
    kind: str
    balance: str