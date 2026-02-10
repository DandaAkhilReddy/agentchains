"""Drop and recreate all database tables."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marketplace.database import drop_db, init_db


async def main():
    print("Dropping all tables...")
    await drop_db()
    print("Creating all tables...")
    await init_db()
    print("Database reset complete.")


if __name__ == "__main__":
    asyncio.run(main())
