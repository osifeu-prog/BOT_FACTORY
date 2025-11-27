from decimal import Decimal

from sqlalchemy.orm import Session

from app import models


def get_or_create_user(
    db: Session,
    telegram_id: int,
    username: str | None = None,
) -> models.User:
    """
    טוען משתמש לפי telegram_id, ואם לא קיים – יוצר חדש.
    משתמש ב-telegram_id כ-PK (אין עמודת id בטבלת users).
    """
    user = (
        db.query(models.User)
        .filter(models.User.telegram_id == telegram_id)
        .first()
    )

    if user:
        # עדכון username אם השתנה
        if username and user.username != username:
            user.username = username
            db.commit()
            db.refresh(user)
        return user

    # יצירת משתמש חדש
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
    עדכון כתובת BNB למשתמש.
    """
    user.bnb_address = address
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_balance(
    db: Session,
    user: models.User,
    delta_slh: float | Decimal,
    tx_type: str,
    from_user: int | None,
    to_user: int | None,
) -> models.Transaction:
    """
    שינוי יתרת SLH למשתמש + יצירת רשומת טרנזקציה בלדג'ר.

    from_user / to_user – מזהי טלגרם (telegram_id), לא מפתח זר לטבלה אחרת.
    """
    delta = Decimal(str(delta_slh))

    current = user.balance_slh or Decimal("0")
    new_balance = current + delta
    user.balance_slh = new_balance

    tx = models.Transaction(
        from_user=from_user,
        to_user=to_user,
        tx_type=tx_type,
        amount_slh=delta,
    )
    db.add(tx)
    db.add(user)
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
    העברת SLH פנימית Off-Chain בין שני משתמשים.
    """
    amount = Decimal(str(amount_slh))
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")

    sender_balance = sender.balance_slh or Decimal("0")
    if sender_balance < amount:
        raise ValueError("Insufficient balance")

    # עדכון יתרות
    sender.balance_slh = sender_balance - amount
    receiver.balance_slh = (receiver.balance_slh or Decimal("0")) + amount

    tx = models.Transaction(
        from_user=sender.telegram_id,
        to_user=receiver.telegram_id,
        tx_type="transfer",
        amount_slh=amount,
    )
    db.add(sender)
    db.add(receiver)
    db.add(tx)
    db.commit()
    db.refresh(sender)
    db.refresh(receiver)
    db.refresh(tx)
    return tx
