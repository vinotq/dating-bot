from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from src.db import engine
from src.models import Base


async def run_migrations() -> None:
    async with engine.begin() as conn:
        print("matching_schema …")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS matching_schema"))
        print("create_all …")
        await conn.run_sync(Base.metadata.create_all)
        print("index swipes(swiped_id, created_at) …")
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_swipes_swiped_created "
                "ON matching_schema.swipes (swiped_id, created_at DESC)"
            )
        )
        print("index messages(match_id, created_at) …")
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_messages_match_created "
                "ON matching_schema.messages (match_id, created_at DESC)"
            )
        )
    print("Миграции применены.")


def main() -> None:
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        print(f"Ошибка миграций: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
