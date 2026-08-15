from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.core.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

LOCK_KEY = 741302001


def run_migrations_offline() -> None:
    context.configure(
        url=settings.platform_database_url_sync,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(settings.platform_database_url_sync, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        connection.execute(text("select pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        try:
            context.configure(connection=connection, target_metadata=None, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.execute(text("select pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            connection.commit()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
