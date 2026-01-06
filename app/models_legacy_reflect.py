from __future__ import annotations

"""
Reflect the live DB into app.database.Base.metadata so Alembic autogenerate/check
does NOT propose dropping existing tables.

This module is intended to be imported by alembic/env.py at runtime on Railway.
"""

import os

from sqlalchemy import MetaData, create_engine

from app.database import Base


def reflect_into_base_metadata() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set (needed for reflection).")

    engine = create_engine(url)
    md = MetaData()
    md.reflect(bind=engine)

    for name, table in md.tables.items():
        if name not in Base.metadata.tables:
            table.tometadata(Base.metadata)


# Reflect at import-time for Alembic env.py usage
reflect_into_base_metadata()