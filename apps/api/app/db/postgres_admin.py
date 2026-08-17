"""Conexão administrativa PostgreSQL resiliente para provisionamento de tenants.

A imagem oficial do PostgreSQL transforma ``POSTGRES_USER`` no superusuário do
cluster durante o primeiro initdb. Por isso uma instalação cujo usuário inicial
é ``scheduler`` pode não possuir o papel ``postgres``. Este módulo tenta a
credencial administrativa explícita e, em seguida, a credencial da plataforma,
sem registrar senhas.
"""

from dataclasses import dataclass

import asyncpg

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class AdminCredentialAttempt:
    source: str
    user: str
    password: str


class PostgresAdminConnectionError(RuntimeError):
    """Nenhuma credencial administrativa configurada conseguiu conectar."""


def _credential_candidates() -> list[AdminCredentialAttempt]:
    # Na imagem oficial postgres, POSTGRES_USER criado no primeiro initdb
    # é o superusuário real do cluster. Tente-o primeiro para não gerar um FATAL
    # artificial em stacks onde o papel `postgres` não existe.
    candidates = [
        AdminCredentialAttempt(
            "POSTGRES_*",
            (settings.postgres_user or "").strip(),
            settings.postgres_password or "",
        ),
        AdminCredentialAttempt(
            "POSTGRES_ADMIN_*",
            (settings.postgres_admin_user or "").strip(),
            settings.postgres_admin_password or "",
        ),
    ]
    unique: list[AdminCredentialAttempt] = []
    seen: set[tuple[str, str]] = set()
    for item in candidates:
        key = (item.user, item.password)
        if not item.user or not item.password or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


async def _has_tenant_admin_capabilities(conn: asyncpg.Connection) -> bool:
    """Confirma que a credencial pode criar/remover banco e papel de tenant."""

    row = await conn.fetchrow(
        """
        select rolsuper, rolcreaterole, rolcreatedb
        from pg_roles
        where rolname=current_user
        """
    )
    if row is None:
        return False
    return bool(row["rolsuper"] or (row["rolcreaterole"] and row["rolcreatedb"]))


async def connect_postgres_admin(
    database: str | None = None,
) -> asyncpg.Connection:
    """Conecta com a primeira credencial administrativa válida.

    Além de autenticar, a credencial precisa ter privilégios suficientes para
    criar/remover os bancos e papéis isolados dos tenants. Uma credencial
    explícita inválida ou sem privilégios não impede o fallback para a
    credencial da plataforma. Senhas nunca são incluídas em logs/exceções.
    """

    attempts: list[dict[str, str]] = []
    last_error: BaseException | None = None
    for candidate in _credential_candidates():
        conn: asyncpg.Connection | None = None
        try:
            conn = await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=candidate.user,
                password=candidate.password,
                database=database or settings.postgres_db,
            )
            if await _has_tenant_admin_capabilities(conn):
                return conn
            attempts.append(
                {
                    "source": candidate.source,
                    "user": candidate.user,
                    "error": "InsufficientPrivilege",
                }
            )
            await conn.close()
            conn = None
        except (asyncpg.PostgresError, OSError) as exc:
            attempts.append(
                {
                    "source": candidate.source,
                    "user": candidate.user,
                    "error": exc.__class__.__name__,
                }
            )
            last_error = exc
            if conn is not None:
                try:
                    await conn.close()
                except Exception:  # noqa: BLE001 - cleanup best effort
                    pass

    error = PostgresAdminConnectionError(
        "Não foi possível abrir conexão administrativa PostgreSQL. "
        f"Tentativas: {attempts or [{'error': 'credenciais ausentes'}]}"
    )
    if last_error is not None:
        raise error from last_error
    raise error
