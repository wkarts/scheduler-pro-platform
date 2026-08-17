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
    candidates = [
        AdminCredentialAttempt(
            "POSTGRES_ADMIN_*",
            (settings.postgres_admin_user or "").strip(),
            settings.postgres_admin_password or "",
        ),
        AdminCredentialAttempt(
            "POSTGRES_*",
            (settings.postgres_user or "").strip(),
            settings.postgres_password or "",
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


async def connect_postgres_admin(
    database: str | None = None,
) -> asyncpg.Connection:
    """Conecta com a primeira credencial administrativa válida.

    A mensagem de erro informa apenas usuários/fontes tentados; senhas nunca são
    incluídas no log ou na exceção.
    """

    attempts: list[dict[str, str]] = []
    last_error: BaseException | None = None
    for candidate in _credential_candidates():
        try:
            return await asyncpg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=candidate.user,
                password=candidate.password,
                database=database or settings.postgres_db,
            )
        except (asyncpg.PostgresError, OSError) as exc:
            attempts.append(
                {
                    "source": candidate.source,
                    "user": candidate.user,
                    "error": exc.__class__.__name__,
                }
            )
            last_error = exc

    error = PostgresAdminConnectionError(
        "Não foi possível abrir conexão administrativa PostgreSQL. "
        f"Tentativas: {attempts or [{'error': 'credenciais ausentes'}]}"
    )
    if last_error is not None:
        raise error from last_error
    raise error
