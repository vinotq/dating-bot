import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://dating_user:dating_pass@localhost:5432/dating_bot"


async def migrate():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            print("Dropping old profiles_age_check constraint...")
            await session.execute(text("""
                ALTER TABLE users_schema.profiles 
                DROP CONSTRAINT IF EXISTS profiles_age_check
            """))
            await session.commit()
            print("Old constraint dropped")
            
            print("Adding new profiles_age_check constraint...")
            await session.execute(text("""
                ALTER TABLE users_schema.profiles 
                ADD CONSTRAINT profiles_age_check 
                CHECK (age >= 14 AND age <= 100)
            """))
            await session.commit()
            print("New constraint added")
            
            print("\nMigration completed successfully!")
            
        except Exception as e:
            await session.rollback()
            print(f"Migration failed: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    print("Starting database migration...\n")
    asyncio.run(migrate())
