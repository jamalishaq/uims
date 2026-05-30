import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://postgres:oyinkan1@localhost:5432/postgres")
    try:
        await conn.execute("CREATE DATABASE university_db_test")
        print("Created university_db_test")
    except Exception as e:
        print(f"Note: {e}")
    finally:
        await conn.close()

asyncio.run(main())
