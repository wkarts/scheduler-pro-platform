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
    sql_path = ROOT / "migrations" / "platform" / "001_platform_init.sql"
    conn = await _connect(settings.postgres_db)
    try:
        await conn.execute(sql_path.read_text(encoding="utf-8"))
        print(f"platform migration applied: {sql_path}")
    finally:
        await conn.close()


async def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "help"
    if command == "migrate-platform":
        await migrate_platform()
        return
    print("Usage: python -m app.cli migrate-platform", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
