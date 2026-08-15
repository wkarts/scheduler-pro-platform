import asyncio
import sys
from pathlib import Path

import asyncpg

from app.core.config import settings


ROOT = Path(__file__).resolve().parents[1]


async def _connect(database: str | None = None):
    return await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        database=database or settings.postgres_db,
    )


async def migrate_platform() -> None:
    migrations_dir = ROOT / "migrations" / "platform"
    conn = await _connect(settings.postgres_db)
    try:
        for sql_path in sorted(migrations_dir.glob("*.sql")):
            await conn.execute(sql_path.read_text(encoding="utf-8"))
            print(f"platform migration applied: {sql_path.name}")
    finally:
        await conn.close()


async def migrate_tenant(database: str) -> None:
    migrations_dir = ROOT / "migrations" / "tenant"
    conn = await _connect(database)
    try:
        for sql_path in sorted(migrations_dir.glob("*.sql")):
            await conn.execute(sql_path.read_text(encoding="utf-8"))
            print(f"tenant migration applied: {database}: {sql_path.name}")
    finally:
        await conn.close()


async def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    if command == "migrate-platform":
        await migrate_platform()
        return
    if command == "migrate-tenant" and len(sys.argv) >= 3:
        await migrate_tenant(sys.argv[2])
        return
    print("Usage: python -m app.cli migrate-platform | migrate-tenant <database>", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
