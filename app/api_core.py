from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException

from .db import db_session
from . import schemas
from .crud_core import (
    get_or_create_user,
    get_or_create_account,
    post_ledger,
    compute_balance,
)

router = APIRouter(prefix="/core", tags=["core"])


@router.post("/users/get_or_create", response_model=schemas.UserOut)
def users_get_or_create(payload: schemas.UserUpsertIn):
    with db_session() as db:
        u = get_or_create_user(
            db,
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
        return schemas.UserOut(
            id=u.id,
            telegram_id=u.telegram_id,
            username=u.username,
            first_name=u.first_name,
            last_name=u.last_name,
            is_admin=bool(u.is_admin),
        )


@router.post("/ledger/credit", response_model=schemas.LedgerPostResult)
def ledger_credit(payload: schemas.LedgerCreditIn):
    try:
        amt = Decimal(payload.amount)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="amount must be a decimal string")

    with db_session() as db:
        u = get_or_create_user(db, telegram_id=payload.telegram_id)
        a = get_or_create_account(db, user_id=u.id, currency=payload.currency, kind=payload.kind)
        row = post_ledger(
            db,
            a.id,
            "CREDIT",
            amt,
            asset=payload.currency,
            memo=payload.memo,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
        )
        return schemas.LedgerPostResult(ok=True, ledger_id=row.id, account_id=a.id)


@router.post("/ledger/debit", response_model=schemas.LedgerPostResult)
def ledger_debit(payload: schemas.LedgerCreditIn):
    try:
        amt = Decimal(payload.amount)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="amount must be a decimal string")

    with db_session() as db:
        u = get_or_create_user(db, telegram_id=payload.telegram_id)
        a = get_or_create_account(db, user_id=u.id, currency=payload.currency, kind=payload.kind)
        row = post_ledger(
            db,
            a.id,
            "DEBIT",
            amt,
            asset=payload.currency,
            memo=payload.memo,
            ref_type=payload.ref_type,
            ref_id=payload.ref_id,
        )
        return schemas.LedgerPostResult(ok=True, ledger_id=row.id, account_id=a.id)


@router.get("/accounts/{telegram_id}/balance", response_model=schemas.BalanceOut)
def account_balance(telegram_id: int, currency: str = "USD", kind: str = "MAIN"):
    with db_session() as db:
        u = get_or_create_user(db, telegram_id=telegram_id)
        a = get_or_create_account(db, user_id=u.id, currency=currency, kind=kind)
        bal = compute_balance(db, a.id)
        return schemas.BalanceOut(
            telegram_id=telegram_id,
            account_id=a.id,
            currency=currency,
            kind=kind,
            balance=str(bal),
        )
