from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from src.db import engine
from src.models import Base


async def run_migrations() -> None:
    async with engine.begin() as conn:
        print("users_schema …")
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS users_schema"))

        print("create_all …")
        await conn.run_sync(Base.metadata.create_all)

        print("columns age_min / age_max (IF NOT EXISTS) …")
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD COLUMN IF NOT EXISTS age_min SMALLINT NOT NULL DEFAULT 14
            """)
        )
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD COLUMN IF NOT EXISTS age_max SMALLINT NOT NULL DEFAULT -1
            """)
        )
        await conn.execute(
            text("ALTER TABLE users_schema.profiles ALTER COLUMN age_max SET DEFAULT -1")
        )

        print("003: age_max / range …")
        await conn.execute(
            text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_max_check")
        )
        await conn.execute(
            text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_range_check")
        )
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD CONSTRAINT profiles_age_max_check
                CHECK (age_max = -1 OR age_max >= 14)
            """)
        )
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD CONSTRAINT profiles_age_range_check
                CHECK (age_max = -1 OR age_min <= age_max)
            """)
        )

        print("004: age / age_min без верхней границы …")
        await conn.execute(
            text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_check")
        )
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD CONSTRAINT profiles_age_check
                CHECK (age >= 14)
            """)
        )
        await conn.execute(
            text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_min_check")
        )
        await conn.execute(
            text("""
                ALTER TABLE users_schema.profiles
                ADD CONSTRAINT profiles_age_min_check
                CHECK (age_min >= 14)
            """)
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
