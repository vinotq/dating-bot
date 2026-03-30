"""
Убрать верхнюю границу возраста в БД (профиль и age_min в настройках поиска).

Ранее migration 002 могла добавить CHECK (age >= 14 AND age <= 100).
"""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://dating_user:dating_pass@localhost:5432/dating_bot"


async def migrate() -> None:
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("Dropping profiles_age_check (remove age <= 100 if present)...")
            await session.execute(
                text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_check")
            )
            await session.commit()

            print("Adding profiles_age_check (age >= 14 only)...")
            await session.execute(
                text("""
                    ALTER TABLE users_schema.profiles
                    ADD CONSTRAINT profiles_age_check
                    CHECK (age >= 14)
                """)
            )
            await session.commit()

            print("Dropping profiles_age_min_check (remove age_min <= 100)...")
            await session.execute(
                text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_min_check")
            )
            await session.commit()

            print("Adding profiles_age_min_check (age_min >= 14 only)...")
            await session.execute(
                text("""
                    ALTER TABLE users_schema.profiles
                    ADD CONSTRAINT profiles_age_min_check
                    CHECK (age_min >= 14)
                """)
            )
            await session.commit()

            print("Migration 004 completed successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Migration failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
