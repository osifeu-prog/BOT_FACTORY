import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Base MUST exist here because models import it: rom app.database import Base
Base = declarative_base()


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()

    # remove wrapping quotes
    if len(u) >= 2 and (u[0] == u[-1]) and (u[0] in ("'", '"')):
        u = u[1:-1].strip()

    # Railway/Heroku style scheme
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]

    return u


# DATABASE_URL required in production, optional in local dev
DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL") or "")
if not DATABASE_URL:
    DATABASE_URL = "sqlite+pysqlite:///./local.db"

engine_kwargs = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    # Import models so they register on Base.metadata
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()