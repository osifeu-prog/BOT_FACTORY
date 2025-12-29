from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List, Tuple
import os

import psycopg2


DDL_INVESTORS = """
CREATE TABLE IF NOT EXISTS investors (
  telegram_id BIGINT PRIMARY KEY,
  username TEXT NULL,
  bnb_address TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

DDL_LEDGER_TX = """
CREATE TABLE IF NOT EXISTS ledger_transactions (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  asset TEXT NOT NULL DEFAULT 'SLH',
  amount NUMERIC(38, 18) NOT NULL CHECK (amount >= 0),

  from_telegram_id BIGINT NULL,
  to_telegram_id BIGINT NULL,

  kind TEXT NOT NULL,           -- e.g. admin_credit, transfer, airdrop, correction
  memo TEXT NULL,

  ref_update_id BIGINT NULL,    -- optional: telegram update_id for traceability
  ref_ext_id TEXT NULL          -- optional: external reference
);
"""

DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ledger_tx_to ON ledger_transactions (to_telegram_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_tx_from ON ledger_transactions (from_telegram_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_tx_created ON ledger_transactions (created_at DESC);
"""


def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return dsn


def _connect():
    dsn = _dsn()
    pw = os.environ.get("PGPASSWORD")
    return psycopg2.connect(dsn, password=pw) if pw else psycopg2.connect(dsn)


def ensure_ledger_tables() -> None:
    """
    Idempotent. Safe to call on every startup.
    """
    conn = _connect()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(DDL_INVESTORS)
            cur.execute(DDL_LEDGER_TX)
            for stmt in [s.strip() for s in DDL_INDEXES.split(";") if s.strip()]:
                cur.execute(stmt)
        finally:
            cur.close()
    finally:
        conn.close()


def upsert_investor(telegram_id: int, username: Optional[str], bnb_address: Optional[str]) -> None:
    conn = _connect()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO investors (telegram_id, username, bnb_address)
                VALUES (%s, %s, %s)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                  username = COALESCE(EXCLUDED.username, investors.username),
                  bnb_address = COALESCE(EXCLUDED.bnb_address, investors.bnb_address),
                  updated_at = NOW();
                """,
                (telegram_id, username, bnb_address),
            )
        finally:
            cur.close()
    finally:
        conn.close()


def credit(telegram_id: int, amount: Decimal, kind: str = "admin_credit", memo: Optional[str] = None,
           ref_update_id: Optional[int] = None, asset: str = "SLH") -> int:
    conn = _connect()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO ledger_transactions (asset, amount, from_telegram_id, to_telegram_id, kind, memo, ref_update_id)
                VALUES (%s, %s, NULL, %s, %s, %s, %s)
                RETURNING id;
                """,
                (asset, str(amount), telegram_id, kind, memo, ref_update_id),
            )
            row = cur.fetchone()
            return int(row[0])
        finally:
            cur.close()
    finally:
        conn.close()


def transfer(from_telegram_id: int, to_telegram_id: int, amount: Decimal, memo: Optional[str] = None,
             ref_update_id: Optional[int] = None, asset: str = "SLH") -> int:
    """
    Simple internal transfer: records one row with from/to.
    Balance is computed net.
    """
    conn = _connect()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        try:
            # Optional: enforce sufficient balance atomically
            cur.execute(
                """
                WITH bal AS (
                  SELECT
                    COALESCE(SUM(CASE WHEN to_telegram_id=%s THEN amount ELSE 0 END),0)
                    - COALESCE(SUM(CASE WHEN from_telegram_id=%s THEN amount ELSE 0 END),0) AS b
                  FROM ledger_transactions
                  WHERE asset=%s AND (to_telegram_id=%s OR from_telegram_id=%s)
                )
                SELECT b FROM bal;
                """,
                (from_telegram_id, from_telegram_id, asset, from_telegram_id, from_telegram_id),
            )
            b = Decimal(str(cur.fetchone()[0]))
            if b < amount:
                raise ValueError(f"insufficient balance: {b} < {amount}")

            cur.execute(
                """
                INSERT INTO ledger_transactions (asset, amount, from_telegram_id, to_telegram_id, kind, memo, ref_update_id)
                VALUES (%s, %s, %s, %s, 'transfer', %s, %s)
                RETURNING id;
                """,
                (asset, str(amount), from_telegram_id, to_telegram_id, memo, ref_update_id),
            )
            row = cur.fetchone()
            return int(row[0])
        finally:
            cur.close()
    finally:
        conn.close()


def get_balance(telegram_id: int, asset: str = "SLH") -> Decimal:
    conn = _connect()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN to_telegram_id=%s THEN amount ELSE 0 END),0)
                  - COALESCE(SUM(CASE WHEN from_telegram_id=%s THEN amount ELSE 0 END),0) AS balance
                FROM ledger_transactions
                WHERE asset=%s AND (to_telegram_id=%s OR from_telegram_id=%s);
                """,
                (telegram_id, telegram_id, asset, telegram_id, telegram_id),
            )
            row = cur.fetchone()
            return Decimal(str(row[0] if row else "0"))
        finally:
            cur.close()
    finally:
        conn.close()


@dataclass(frozen=True)
class LedgerRow:
    id: int
    created_at: str
    asset: str
    amount: str
    direction: str  # IN/OUT
    other_party: Optional[int]
    kind: str
    memo: Optional[str]


def get_history(telegram_id: int, limit: int = 10, asset: str = "SLH") -> List[LedgerRow]:
    limit = max(1, min(int(limit), 50))
    conn = _connect()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, created_at, asset, amount, from_telegram_id, to_telegram_id, kind, memo
                FROM ledger_transactions
                WHERE asset=%s AND (to_telegram_id=%s OR from_telegram_id=%s)
                ORDER BY id DESC
                LIMIT %s;
                """,
                (asset, telegram_id, telegram_id, limit),
            )
            rows = []
            for (id_, created_at, asset_, amount, from_id, to_id, kind, memo) in cur.fetchall():
                if to_id == telegram_id:
                    direction = "IN"
                    other = from_id
                else:
                    direction = "OUT"
                    other = to_id
                rows.append(LedgerRow(
                    id=int(id_),
                    created_at=str(created_at),
                    asset=str(asset_),
                    amount=str(amount),
                    direction=direction,
                    other_party=int(other) if other is not None else None,
                    kind=str(kind),
                    memo=str(memo) if memo is not None else None,
                ))
            return rows
        finally:
            cur.close()
    finally:
        conn.close()