# app/models.py
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    DateTime,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=True)
    bnb_address = Column(String, nullable=True)

    # יתרה פנימית ב-SLH (Off-Chain)
    balance_slh = Column(Numeric(24, 6), nullable=False, default=Decimal("0"))

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id} username={self.username}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # מזהי טלגרם (לא מפתחות זרים כדי לשמור על פשטות)
    from_user = Column(BigInteger, nullable=True)  # יכול להיות None (admin_credit)
    to_user = Column(BigInteger, nullable=True)

    # כמות ב-SLH
    amount_slh = Column(Numeric(24, 6), nullable=False)

    # טיפוס טרנזקציה: "admin_credit", "transfer" וכו'
    tx_type = Column(String(50), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} "
            f"type={self.tx_type} "
            f"from={self.from_user} to={self.to_user} "
            f"amount={self.amount_slh}>"
        )
