import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# בסיס המודלים (חשוב שיהיה כאן כי מודלים מייבאים אותו)
Base = declarative_base()


def _normalize_db_url(url: str) -> str:
    u = (url or "").strip()

    # remove wrapping quotes (common when pasted)
    if len(u) >= 2 and (u[0] == u[-1]) and (u[0] in ("'", '"')):
        u = u[1:-1].strip()

    # ignore CI/template placeholders like: ${{Postgres.DATABASE_URL}}
    if "${{" in u or "}}" in u:
        return ""

    # Railway/Heroku style scheme
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]

    return u


# DB URL from environment (Railway), optional in local dev.
DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL") or "")

# Local fallback
if not DATABASE_URL:
    DATABASE_URL = "sqlite+pysqlite:///./local.db"

engine_kwargs = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """
    יצירת טבלאות חסרות לפי המודלים.
    """
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency סטנדרטי לשימוש ב-Session דרך FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
