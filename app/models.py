from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, BigInteger, String, Numeric, DateTime, ForeignKey

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=True)
    bnb_address = Column(String, nullable=True)
    balance_slh = Column(Numeric(precision=24, scale=6), default=Decimal("0"))


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    from_user = Column(BigInteger, nullable=True)
    to_user = Column(BigInteger, nullable=True)
    amount_slh = Column(Numeric(precision=24, scale=6), nullable=False)
    tx_type = Column(String, default="transfer")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
