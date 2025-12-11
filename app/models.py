import datetime as dt

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Numeric,
    DateTime,
    Integer,
    Boolean,
    func,
)

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=True)
    bnb_address = Column(String, nullable=True)
    balance_slh = Column(Numeric(20, 8), default=0)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_type = Column(
        String,
        nullable=False,
    )  # admin_credit / admin_debit / internal_transfer
    from_user = Column(BigInteger, nullable=True)  # Telegram ID
    to_user = Column(BigInteger, nullable=True)  # Telegram ID
    amount_slh = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    note = Column(String, nullable=True)


# =========================
#  רפררלים + SELA פנימי
# =========================

class ReferralLink(Base):
    """
    קישור הפניה בסיסי לכל משתמש.
    לדוגמה: https://t.me/<bot>?start=ref_<telegram_id>
    שדה code מאפשר בעתיד לייצר קודים שונים (קמפיינים).
    """
    __tablename__ = "referral_links"

    id = Column(Integer, primary_key=True, index=True)
    owner_telegram_id = Column(BigInteger, index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    is_active = Column(Boolean, default=True)


class ReferralReward(Base):
    """
    לוג של כל “אירוע SELA”:
    - פרס על שיתוף (0.00001 SELA)
    - פרס על הפקדה (1 SELA לכל 10,000 ₪)
    """
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    delta_sela = Column(Numeric(20, 8), nullable=False)
    reason = Column(String, nullable=True)  # "share", "deposit_bonus", ...
    meta = Column(String, nullable=True)  # שדה טקסט חופשי (קמפיין, tx id וכו')
    created_at = Column(DateTime, default=dt.datetime.utcnow)
