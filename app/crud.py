from sqlalchemy.orm import Session
from decimal import Decimal

from app import models


def get_or_create_user(db: Session, telegram_id: int, username: str | None = None) -> models.User:
    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
    if user:
        if username and user.username != username:
            user.username = username
            db.commit()
        return user

    user = models.User(telegram_id=telegram_id, username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def set_bnb_address(db: Session, user: models.User, address: str) -> models.User:
    user.bnb_address = address
    db.commit()
    db.refresh(user)
    return user


def change_balance(
    db: Session,
    user: models.User,
    delta_slh: float,
    tx_type: str,
    from_user: int | None = None,
    to_user: int | None = None,
):
    new_balance = (user.balance_slh or 0) + Decimal(str(delta_slh))
    user.balance_slh = new_balance

    tx = models.Transaction(
        from_user=from_user,
        to_user=to_user,
        amount_slh=Decimal(str(delta_slh)),
        status="completed",
        type=tx_type,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def internal_transfer(db: Session, sender: models.User, receiver: models.User, amount_slh: float):
    from decimal import Decimal

    amount_dec = Decimal(str(amount_slh))

    if sender.balance_slh is None or sender.balance_slh < amount_dec:
        raise ValueError("Insufficient balance")

    sender.balance_slh = sender.balance_slh - amount_dec
    receiver.balance_slh = (receiver.balance_slh or 0) + amount_dec

    tx = models.Transaction(
        from_user=sender.telegram_id,
        to_user=receiver.telegram_id,
        amount_slh=amount_dec,
        status="completed",
        type="internal",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
