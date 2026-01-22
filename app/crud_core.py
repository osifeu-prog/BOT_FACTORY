from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from .models import User, Account, LedgerEntry


def get_or_create_user(db: Session, telegram_id: int, username: str | None = None,
                       first_name: str | None = None, last_name: str | None = None) -> User:
    user = db.execute(select(User).where(User.telegram_id == telegram_id)).scalar_one_or_none()
    if user:
        changed = False
        for field, value in [("username", username), ("first_name", first_name), ("last_name", last_name)]:
            if value is not None and getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if changed:
            db.add(user)
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        is_admin=False,
    )
    db.add(user)
    db.flush()
    return user


def get_or_create_account(db: Session, user_id: int, currency: str = "USD", kind: str = "MAIN") -> Account:
    acct = db.execute(
        select(Account).where(Account.user_id == user_id, Account.currency == currency, Account.kind == kind)
    ).scalar_one_or_none()
    if acct:
        return acct
    acct = Account(user_id=user_id, currency=currency, kind=kind, status="ACTIVE")
    db.add(acct)
    db.flush()
    return acct


def post_ledger(db: Session, account_id: int, direction: str, amount: Decimal,
                asset: str = "USD", memo: str | None = None, ref_type: str | None = None, ref_id: str | None = None) -> LedgerEntry:
    if direction not in ("DEBIT", "CREDIT"):
        raise ValueError("direction must be DEBIT or CREDIT")
    if amount < 0:
        raise ValueError("amount must be >= 0")

    row = LedgerEntry(
        account_id=account_id,
        direction=direction,
        amount=amount,
        asset=asset,
        memo=memo,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(row)
    db.flush()
    return row


def compute_balance(db: Session, account_id: int) -> Decimal:
    # CREDIT adds, DEBIT subtracts
    signed = case(
        (LedgerEntry.direction == "CREDIT", LedgerEntry.amount),
        else_=-LedgerEntry.amount,
    )
    val = db.execute(select(func.coalesce(func.sum(signed), 0)).where(LedgerEntry.account_id == account_id)).scalar_one()
    return Decimal(val)