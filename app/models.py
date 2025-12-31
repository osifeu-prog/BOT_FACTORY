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
    أ—ع©أ—â€کأ—إ“أ—ع¾ أ—â€چأ—آ©أ—ع¾أ—â€چأ—آ©أ—â„¢أ—â€Œ أ¢â‚¬â€œ أ—â€چأ—â€¢أ—ع¾أ—ع¯أ—â€Œ أ—إ“أ—طŒأ—â€؛أ—â„¢أ—â€چأ—â€‌ أ—â€‌أ—آ§أ—â„¢أ—â„¢أ—â€چأ—ع¾ أ—â€کأ—آ¤أ—â€¢أ—طŒأ—ع©أ—â€™أ—آ¨أ—طŒ.

    أ—â€”أ—آ©أ—â€¢أ—â€ک:
    - أ—ع¯أ—â„¢أ—ع؛ أ—آ¢أ—â€چأ—â€¢أ—â€œأ—â€‌ id.
    - telegram_id أ—â€‌أ—â€¢أ—ع¯ أ—â€‌-Primary Key.
    """

    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(255), index=True, nullable=True)
    bnb_address = Column(String(255), nullable=True)
    balance_slh = Column(Numeric(24, 6), nullable=False, default=0)


class Transaction(Base):
    """
    أ—ع©أ—â€کأ—إ“أ—ع¾ أ—ع©أ—آ¨أ—آ أ—â€“أ—آ§أ—آ¦أ—â„¢أ—â€¢أ—ع¾ أ—آ¤أ—آ أ—â„¢أ—â€چأ—â„¢أ—â€¢أ—ع¾ (Off-Chain Ledger).
    """

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # أ—â€چأ—â€“أ—â€‌أ—â„¢ أ—ع©أ—إ“أ—â€™أ—آ¨أ—â€Œ (أ—إ“أ—ع¯ FK أ—آ¤أ—â€¢أ—آ¨أ—â€چأ—إ“أ—â„¢, أ—آ¤أ—آ©أ—â€¢أ—ع© أ—آ©أ—â€چأ—â„¢أ—آ¨أ—â€‌ أ—آ©أ—إ“ أ—â€‌-ID)
    from_user = Column(BigInteger, nullable=True)
    to_user = Column(BigInteger, nullable=True)

    amount_slh = Column(Numeric(24, 6), nullable=False)
    tx_type = Column(String(50), nullable=False)
from app.models_investments import Deposit, SLHLedger, RedemptionRequest  # noqa: F401
