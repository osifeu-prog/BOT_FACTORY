from __future__ import annotations

import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session


def _require_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


class Base(DeclarativeBase):
    pass


ENGINE = create_engine(
    _require_database_url(),
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=ENGINE, class_=Session, autoflush=False, autocommit=False)


@contextmanager
def db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()