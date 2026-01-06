from __future__ import annotations

"""
Reflect live DB schema into a *separate* MetaData and merge only missing tables
into app.database.Base.metadata so Alembic autogenerate/check won't propose drops.

Important: We must NOT redefine tables that already exist in Base.metadata
(e.g., deposits defined by ORM models), otherwise SQLAlchemy raises:
"Table 'X' is already defined for this MetaData instance".
"""

import os

from sqlalchemy import MetaData, create_engine

from app.database import Base


def reflect_missing_tables_into_base_metadata() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set (needed for reflection).")

    engine = create_engine(url)

    reflected = MetaData()
    reflected.reflect(bind=engine)

    existing = set(Base.metadata.tables.keys())

    for name, table in reflected.tables.items():
        if name in existing:
            continue
        table.to_metadata(Base.metadata)


# Reflect at import-time for Alembic env.py usage
reflect_missing_tables_into_base_metadata()