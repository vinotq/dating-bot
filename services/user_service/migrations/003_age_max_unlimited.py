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
            print("Dropping old age_max / range constraints...")
            await session.execute(
                text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_max_check")
            )
            await session.execute(
                text("ALTER TABLE users_schema.profiles DROP CONSTRAINT IF EXISTS profiles_age_range_check")
            )
            await session.commit()

            print("Setting default age_max to -1 (no upper limit)...")
            await session.execute(
                text("ALTER TABLE users_schema.profiles ALTER COLUMN age_max SET DEFAULT -1")
            )
            await session.commit()

            print("Adding updated check constraints...")
            await session.execute(
                text("""
                    ALTER TABLE users_schema.profiles
                    ADD CONSTRAINT profiles_age_max_check
                    CHECK (age_max = -1 OR age_max >= 14)
                """)
            )
            await session.execute(
                text("""
                    ALTER TABLE users_schema.profiles
                    ADD CONSTRAINT profiles_age_range_check
                    CHECK (age_max = -1 OR age_min <= age_max)
                """)
            )
            await session.commit()
            print("Migration 003 completed successfully.")
        except Exception as e:
            await session.rollback()
            print(f"Migration failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
