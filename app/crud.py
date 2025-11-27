from decimal import Decimal
from sqlalchemy.orm import Session

from app import models


def get_or_create_user(db: Session, telegram_id: int, username: str | None):
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if user:
        if username and user.username != username:
            user.username = username
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    user = models.User(telegram_id=telegram_id, username=username, balance_slh=Decimal("0"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_bnb_address(db: Session, user: models.User, address: str):
    user.bnb_address = address
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def change_balance(
    db: Session,
    user: models.User,
    delta_slh: float | Decimal,
    tx_type: str = "admin_credit",
    from_user: int | None = None,
    to_user: int | None = None,
):
    amount = Decimal(str(delta_slh))
    if user.balance_slh is None:
        user.balance_slh = Decimal("0")
    new_balance = user.balance_slh + amount
    if new_balance < 0:
        raise ValueError("Insufficient balance")

    user.balance_slh = new_balance
    db.add(user)

    tx = models.Transaction(
        from_user=from_user,
        to_user=to_user,
        amount_slh=amount,
        tx_type=tx_type,
    )
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
):
    amount = Decimal(str(amount_slh))
    if sender.balance_slh is None:
        sender.balance_slh = Decimal("0")
    if sender.balance_slh < amount:
        raise ValueError("Insufficient balance for transfer")

    sender.balance_slh -= amount
    if receiver.balance_slh is None:
        receiver.balance_slh = Decimal("0")
    receiver.balance_slh += amount

    db.add(sender)
    db.add(receiver)

    tx = models.Transaction(
        from_user=sender.telegram_id,
        to_user=receiver.telegram_id,
        amount_slh=amount,
        tx_type="internal_transfer",
    )
    db.add(tx)
    db.commit()
    db.refresh(sender)
    db.refresh(receiver)
    db.refresh(tx)
    return tx
