from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- App imports ----
# IMPORTANT: ensure models are imported so metadata contains tables
from app.database import Base  # noqa: E402
import app.models_investments  # noqa: F401,E402
import app.models_legacy_reflect  # noqa: F401,E402
import app.models  # noqa: F401,E402

target_metadata = Base.metadata


def _get_database_url() -> str:
    # Railway provides DATABASE_URL
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Set it in env (Railway Variables) before running migrations.")
    return url


def run_migrations_offline() -> None:
    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Inject URL from env into Alembic config
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = _get_database_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# After ORM models are imported, merge missing legacy tables into metadata (no collisions)
app.models_legacy_reflect.reflect_missing_tables_into_base_metadata()
