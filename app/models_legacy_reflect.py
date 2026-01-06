"""
Reflect live DB schema into a separate MetaData and merge ONLY missing tables
into app.database.Base.metadata.

IMPORTANT:
- Do NOT run reflection at import-time (it can collide with ORM models like users/deposits).
- Alembic env.py will call reflect_missing_tables_into_base_metadata() explicitly AFTER importing ORM models.
"""

import os
from sqlalchemy import MetaData, create_engine
from app.database import Base


def reflect_missing_tables_into_base_metadata() -> None:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        return

    engine = create_engine(url)

    reflected = MetaData()
    reflected.reflect(bind=engine)

    existing = set(Base.metadata.tables.keys())

    for name, table in reflected.tables.items():
        if name in existing:
            continue
        table.to_metadata(Base.metadata)