# app/crud.py
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app import models


def _to_decimal(value) -> Decimal:
    """
    המרה בטוחה ל-Decimal מכל סוג מספרי / מחרוזת.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


# ===== Users =====


def get_or_create_user(
    db: Session,
    telegram_id: int,
    username: Optional[str] = None,
) -> models.User:
    """
    מאחזר משתמש לפי telegram_id, ואם לא קיים – יוצר חדש עם balance_slh=0.
    """
    user = (
        db.query(models.User)
        .filter(models.User.telegram_id == telegram_id)
        .first()
    )
    if user:
        # עדכון username אם התעדכן בטלגרם
        if username and user.username != username:
            user.username = username
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    user = models.User(
        telegram_id=telegram_id,
        username=username,
        balance_slh=Decimal("0"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_bnb_address(db: Session, user: models.User, address: str) -> models.User:
    """
    שמירת כתובת BNB למשתמש.
    """
    user.bnb_address = address
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ===== Ledger operations =====


def change_balance(
    db: Session,
    user: models.User,
    delta_slh: float | Decimal,
    tx_type: str,
    from_user: Optional[int],
    to_user: Optional[int],
) -> models.Transaction:
    """
    משנה יתרה של משתמש ב-+/- SLH ויוצר רשומת טרנזקציה.
    משמש גם לאדמין (/admin_credit).
    """
    delta = _to_decimal(delta_slh)
    current = _to_decimal(user.balance_slh or 0)
    new_balance = current + delta

    user.balance_slh = new_balance

    tx = models.Transaction(
        from_user=from_user,
        to_user=to_user,
        amount_slh=delta,
        tx_type=tx_type,
    )

    db.add(user)
    db.add(tx)
    db.commit()
    db.refresh(user)
    db.refresh(tx)

    return tx


def internal_transfer(
    db: Session,
    sender: models.User,
    receiver: models.User,
    amount_slh: float | Decimal,
) -> models.Transaction:
    """
    העברת SLH פנימית בין שני משתמשים.
    """
    amount = _to_decimal(amount_slh)

    sender_balance = _to_decimal(sender.balance_slh or 0)
    if amount <= 0:
        raise ValueError("Transfer amount must be greater than zero.")
    if sender_balance < amount:
        raise ValueError("Insufficient balance for this transfer.")

    # עדכון יתרות
    sender.balance_slh = sender_balance - amount
    receiver.balance_slh = _to_decimal(receiver.balance_slh or 0) + amount

    tx = models.Transaction(
        from_user=sender.telegram_id,
        to_user=receiver.telegram_id,
        amount_slh=amount,
        tx_type="transfer",
    )

    db.add(sender)
    db.add(receiver)
    db.add(tx)
    db.commit()
    db.refresh(sender)
    db.refresh(receiver)
    db.refresh(tx)

    return tx
