from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from src.db import engine
from src.models import Base


async def run_migrations() -> None:
    async with engine.begin() as conn:
        print("ranking_schema …")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS ranking_schema"))
        print("create_all …")
        await conn.run_sync(Base.metadata.create_all)
    print("Миграции применены.")


def main() -> None:
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        print(f"Ошибка миграций: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
