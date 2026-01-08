"""
Reflect live DB schema into a separate MetaData and merge ONLY missing tables
into Base.metadata.

If a SQLAlchemy Connection is provided (recommended for Alembic),
use it to respect the same search_path/schema and permissions.
"""

import os
from sqlalchemy import MetaData, create_engine
from app.database import Base


def reflect_missing_tables_into_base_metadata(connection=None) -> None:
    if connection is None:
        url = (os.getenv("DATABASE_URL") or "").strip()
        if not url:
            return
        engine = create_engine(url)
        connection = engine.connect()
        close_conn = True
    else:
        close_conn = False

    try:
        reflected = MetaData()
        reflected.reflect(bind=connection)

        existing = set(Base.metadata.tables.keys())
        for name, table in reflected.tables.items():
            if name in existing:
                continue
            table.to_metadata(Base.metadata)
    finally:
        if close_conn:
            connection.close()