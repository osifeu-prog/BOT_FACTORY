from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- IMPORTANT: import Base + all model modules so Base.metadata is complete ---
from app.database import Base  # noqa: E402
import app.models  # noqa: F401
import app.models_investments  # noqa: F401

target_metadata = Base.metadata


def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
    if not url:
        url = config.get_main_option("sqlalchemy.url")
    return (url or "").strip().strip('"').strip("'")


def run_migrations_offline() -> None:
    url = _get_db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_db_url()
    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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