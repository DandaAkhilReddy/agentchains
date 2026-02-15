"""Drop and recreate all database tables with optional content-store cleanup."""

from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marketplace.database import drop_db, init_db

ROOT = Path(__file__).resolve().parent.parent
CONTENT_STORE_DIRS = [
    ROOT / "data" / "content_store",
    ROOT / "marketplace" / "data" / "content_store",
]


def _purge_content_store() -> None:
    removed = 0
    for folder in CONTENT_STORE_DIRS:
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
    if removed:
        print("Purged local content-store artifacts.")
    else:
        print("No local content-store artifacts found.")


async def _reset_db() -> None:
    print("Dropping all tables...")
    await drop_db()
    print("Creating all tables...")
    await init_db()
    print("Database reset complete.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset local database and optionally purge content-store files.")
    parser.add_argument(
        "--purge-content-store",
        action="store_true",
        help="Also remove local content-store files to avoid stale/demo payload reuse.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.purge_content_store:
        _purge_content_store()
    asyncio.run(_reset_db())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
