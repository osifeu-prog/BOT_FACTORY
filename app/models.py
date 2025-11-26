from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(64), index=True, nullable=True)
    bnb_address = Column(String(64), nullable=True)
    balance_slh = Column(Numeric(24, 8), default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions_sent = relationship(
        "Transaction", back_populates="sender", foreign_keys="Transaction.from_user"
    )
    transactions_received = relationship(
        "Transaction", back_populates="receiver", foreign_keys="Transaction.to_user"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    from_user = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True)
    to_user = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True)
    amount_slh = Column(Numeric(24, 8), nullable=False)
    status = Column(String(20), default="completed")
    type = Column(String(32), default="internal")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("User", foreign_keys=[from_user], back_populates="transactions_sent")
    receiver = relationship("User", foreign_keys=[to_user], back_populates="transactions_received")
