from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from marketplace.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# Engine config: PostgreSQL needs connection pool settings, SQLite does not
_engine_kwargs: dict = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # Recycle connections every 30 min (prevent stale connections)
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# SQLite-only: Enable WAL mode and busy_timeout for concurrent access.
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


class Base(DeclarativeBase):
    pass


_SQLITE_COLUMN_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "data_listings": [
        ("trust_status", "TEXT NOT NULL DEFAULT 'pending_verification'"),
        ("trust_score", "INTEGER NOT NULL DEFAULT 0"),
        ("verification_summary_json", "TEXT DEFAULT '{}'"),
        ("provenance_json", "TEXT DEFAULT '{}'"),
        ("verification_updated_at", "DATETIME"),
    ],
}


def _sqlite_table_exists(sync_conn, table: str) -> bool:
    row = sync_conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return bool(row)


def _sqlite_has_column(sync_conn, table: str, column: str) -> bool:
    rows = sync_conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _apply_sqlite_compat_migrations(sync_conn) -> None:
    """Apply lightweight additive SQLite migrations for local developer DBs."""
    for table, migrations in _SQLITE_COLUMN_MIGRATIONS.items():
        if not _sqlite_table_exists(sync_conn, table):
            continue
        for column, ddl in migrations:
            if _sqlite_has_column(sync_conn, table, column):
                continue
            sync_conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if _is_sqlite:
            await conn.run_sync(_apply_sqlite_compat_migrations)


async def drop_db():
    """Drop all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def dispose_engine():
    """Dispose of the engine connection pool. Call on shutdown."""
    await engine.dispose()
