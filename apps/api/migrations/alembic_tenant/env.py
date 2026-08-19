import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

from app.core.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

LOCK_KEY = 741302002


def tenant_url() -> str:
    database = os.getenv("ALEMBIC_TENANT_DATABASE") or settings.dev_tenant_database
    user = os.getenv("ALEMBIC_TENANT_USER") or settings.dev_tenant_database_user
    password = os.getenv("ALEMBIC_TENANT_PASSWORD") or settings.dev_tenant_database_password
    return settings.tenant_database_url_sync(database, user, password)


def run_migrations_offline() -> None:
    context.configure(
        url=tenant_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(tenant_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # pg_advisory_lock é session-level. Confirme o SELECT do lock antes da
        # transação Alembic para que uma migration abortada não deixe o próprio
        # comando de unlock preso em InFailedSqlTransaction.
        connection.execute(text("select pg_advisory_lock(:key)"), {"key": LOCK_KEY})
        connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=None,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            # Se context.run_migrations() falhar, PostgreSQL mantém a transação
            # em estado aborted. Rollback é obrigatório antes de qualquer SQL.
            if connection.in_transaction():
                connection.rollback()
            connection.execute(
                text("select pg_advisory_unlock(:key)"),
                {"key": LOCK_KEY},
            )
            connection.commit()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
