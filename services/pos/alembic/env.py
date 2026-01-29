"""Alembic environment configuration."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.models.base import Base
from app.models.pos import (  # noqa: F401 — imported for metadata registration
    # Core transaction models
    Transaction,
    TransactionLineItem,
    Payment,
    Receipt,
    Refund,
    # Tax and discount models
    TaxRate,
    Discount,
    # Cash drawer and shift models
    CashDrawer,
    Shift,
    # Reconciliation models
    DailyReconciliation,
    # External integration models
    ExternalPOSIntegration,
    POSSyncLog,
    # Audit and fraud models
    AuditLog,
    FraudAlert,
    # Tip management models
    TipPool,
    TipDistribution,
    # Currency and receipt template models
    Currency,
    ReceiptTemplate,
)

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
