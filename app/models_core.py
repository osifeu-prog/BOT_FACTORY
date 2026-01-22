from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Sequence,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, Sequence("users_id_seq"), primary_key=True)

    # DB has BOTH: unique constraint users_telegram_id_key + non-unique index ix_users_telegram_id
    telegram_id = Column(BigInteger, nullable=False)

    username = Column(Text, nullable=True)
    first_name = Column(Text, nullable=True)
    last_name = Column(Text, nullable=True)

    is_admin = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("telegram_id", name="users_telegram_id_key"),
        Index("ix_users_telegram_id", "telegram_id"),
    )


class Account(Base):
    __tablename__ = "accounts"

    # DB: accounts.id exists (bigserial)
    id = Column(BigInteger, Sequence("accounts_id_seq"), primary_key=True)

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    currency = Column(Text, nullable=False, server_default="USD")
    kind = Column(Text, nullable=False, server_default="MAIN")
    status = Column(Text, nullable=False, server_default="ACTIVE")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "currency", "kind", name="accounts_user_id_currency_kind_key"),
    )
class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(BigInteger, Sequence("ledger_entries_id_seq"), primary_key=True)
    account_id = Column(BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)

    direction = Column(Text, nullable=False)  # DB has CHECK constraint
    amount = Column(Numeric(38, 18), nullable=False)  # DB has CHECK amount>=0
    asset = Column(Text, nullable=False, server_default="USD")

    ref_type = Column(Text, nullable=True)
    ref_id = Column(Text, nullable=True)
    memo = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ledger_entries_amount_check"),
        CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ledger_entries_direction_check"),
        # DB index is (account_id, created_at DESC)
        Index("ix_ledger_account_created_at", account_id, created_at.desc()),
    )