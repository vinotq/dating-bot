import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://dating_user:dating_pass@localhost:5432/dating_bot"


async def migrate():
    """Run the migration."""
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            result = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'users_schema' 
                AND table_name = 'profiles' 
                AND column_name IN ('age_min', 'age_max')
            """))
            existing_columns = [row[0] for row in result.fetchall()]
            
            if "age_min" in existing_columns and "age_max" in existing_columns:
                print("Columns age_min and age_max already exist")
            else:
                if "age_min" not in existing_columns:
                    print("Adding age_min column...")
                    await session.execute(text("""
                        ALTER TABLE users_schema.profiles 
                        ADD COLUMN IF NOT EXISTS age_min SMALLINTEGER NOT NULL DEFAULT 14
                    """))
                    await session.commit()
                    print("age_min column added")
                
                if "age_max" not in existing_columns:
                    print("Adding age_max column...")
                    await session.execute(text("""
                        ALTER TABLE users_schema.profiles 
                        ADD COLUMN IF NOT EXISTS age_max SMALLINTEGER NOT NULL DEFAULT 99
                    """))
                    await session.commit()
                    print("age_max column added")
            
            print("🔄 Updating existing profiles with default age ranges...")
            result = await session.execute(text("""
                UPDATE users_schema.profiles 
                SET age_min = 14, age_max = 99 
                WHERE age_min IS NULL OR age_max IS NULL
                OR age_min < 14 OR age_max > 99
                OR age_min > age_max
            """))
            await session.commit()
            updated_count = result.rowcount
            print(f"Updated {updated_count} profiles with valid age ranges")
            
            print("Adding check constraints...")
            try:
                await session.execute(text("""
                    ALTER TABLE users_schema.profiles 
                    ADD CONSTRAINT profiles_age_min_check 
                    CHECK (age_min >= 14 AND age_min <= 100)
                """))
                await session.commit()
                print("age_min check constraint added")
            except Exception as e:
                print(f"age_min constraint may already exist: {e}")
                await session.rollback()
            
            try:
                await session.execute(text("""
                    ALTER TABLE users_schema.profiles 
                    ADD CONSTRAINT profiles_age_max_check 
                    CHECK (age_max >= 14 AND age_max <= 100)
                """))
                await session.commit()
                print("age_max check constraint added")
            except Exception as e:
                print(f"age_max constraint may already exist: {e}")
                await session.rollback()
            
            try:
                await session.execute(text("""
                    ALTER TABLE users_schema.profiles 
                    ADD CONSTRAINT profiles_age_range_check 
                    CHECK (age_min <= age_max)
                """))
                await session.commit()
                print("age_range check constraint added")
            except Exception as e:
                print(f"age_range constraint may already exist: {e}")
                await session.rollback()
            
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
