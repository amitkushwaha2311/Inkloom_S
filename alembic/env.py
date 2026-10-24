import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.domain.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target metadata for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url with application settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # compare_type=False suppresses false-positive VARCHAR→Enum diffs on SQLite
    # (native_enum=False enums are stored as VARCHAR; Python validates the values)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    ``async_engine_from_config`` does not read ``connect_args`` from
    application settings automatically.  We must pass ``ssl`` explicitly
    so that ``alembic upgrade head`` can connect to Supabase (or any other
    managed PostgreSQL that requires TLS) the same way the application
    server does via ``build_engine``.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    # Build connect_args for asyncpg SSL — mirrors build_engine() in database.py.
    engine_kwargs: dict = {"poolclass": pool.NullPool}
    ssl_mode = settings.DB_SSL_MODE.strip().lower()
    if ssl_mode and not settings.DATABASE_URL.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"ssl": ssl_mode}

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        **engine_kwargs,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
