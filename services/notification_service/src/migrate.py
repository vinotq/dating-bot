from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from src.db import engine
from src.models import Base


async def run_migrations() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS notification_schema"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_notifications_user_id "
            "ON notification_schema.notifications (user_id, created_at DESC)"
        ))
    print("Миграции применены.")


def main() -> None:
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
