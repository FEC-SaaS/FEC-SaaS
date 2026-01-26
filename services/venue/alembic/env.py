"""
Alembic environment configuration for Venue Service.

Uses synchronous psycopg2 driver for migrations while the application
uses asyncpg for async database operations.
"""

from logging.config import fileConfig

from sqlalchemy import pool, create_engine

from alembic import context

# Import models for autogenerate
from app.models.base import Base
from app.models.venue import (
    Venue,
    VenueHours,
    VenueSpecialHours,
    VenueSetting,
    VenueFeature,
    VenueAIConfig,
    VenuePerformance,
    VenueContact,
    VenueImage,
)
from app.config import get_settings

settings = get_settings()

# Alembic Config object
config = context.config

# Override sqlalchemy.url from settings (use sync driver for migrations)
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Uses synchronous psycopg2 connection for Alembic migrations.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
