"""
Reflect live DB schema into a separate MetaData and merge ONLY missing tables
into app.database.Base.metadata. This prevents Alembic autogenerate/check from
proposing DROPs for legacy tables that exist in DB but don't have ORM models.

Important: must run AFTER ORM models are imported, otherwise reflected tables
may collide with ORM-defined tables (e.g., deposits).
"""

import os
from sqlalchemy import MetaData, create_engine
from app.database import Base


def reflect_missing_tables_into_base_metadata() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        # On Railway, DATABASE_URL should exist. If not, do nothing.
        return

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