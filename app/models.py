from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Numeric,
    DateTime,
    Integer,
)
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """
    ×ک×‘×œ×ھ ×‍×©×ھ×‍×©×™×‌ â€“ ×‍×•×ھ×گ×‌ ×œ×،×›×™×‍×” ×”×§×™×™×‍×ھ ×‘×¤×•×،×ک×’×¨×،.

    ×—×©×•×‘:
    - ×گ×™×ں ×¢×‍×•×“×” id.
    - telegram_id ×”×•×گ ×”-Primary Key.
    """

    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(255), index=True, nullable=True)
    bnb_address = Column(String(255), nullable=True)
    balance_slh = Column(Numeric(24, 6), nullable=False, default=0)


class Transaction(Base):
    """
    ×ک×‘×œ×ھ ×ک×¨× ×–×§×¦×™×•×ھ ×¤× ×™×‍×™×•×ھ (Off-Chain Ledger).
    """

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ×‍×–×”×™ ×ک×œ×’×¨×‌ (×œ×گ FK ×¤×•×¨×‍×œ×™, ×¤×©×•×ک ×©×‍×™×¨×” ×©×œ ×”-ID)
    from_user = Column(BigInteger, nullable=True)
    to_user = Column(BigInteger, nullable=True)

    amount_slh = Column(Numeric(24, 6), nullable=False)
    tx_type = Column(String(50), nullable=False)
from app.models_investments import Deposit, SLHLedger, RedemptionRequest  # noqa: F401
