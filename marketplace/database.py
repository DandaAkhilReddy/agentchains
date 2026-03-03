import re

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from marketplace.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

# Engine config: PostgreSQL needs connection pool settings, SQLite does not
_engine_kwargs: dict = {"echo": False}
if not _is_sqlite:
    _engine_kwargs.update({
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
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


_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_ALLOWED_MIGRATION_TABLES = frozenset(_SQLITE_COLUMN_MIGRATIONS.keys())


def _validate_identifier(value: str, label: str) -> str:
    """Validate a SQL identifier to prevent injection."""
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def _sqlite_has_column(sync_conn, table: str, column: str) -> bool:
    if table not in _ALLOWED_MIGRATION_TABLES:
        raise ValueError(f"Table {table!r} not in allowed migration tables")
    _validate_identifier(table, "table name")
    _validate_identifier(column, "column name")
    # Use parameterized sqlite_master query instead of PRAGMA to avoid any
    # SQL injection risk from string interpolation in PRAGMA statements.
    row = sync_conn.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    if not row or not row[0]:
        return False
    # Parse the CREATE TABLE statement to check for column presence
    create_sql = row[0]
    # Match column name as a word boundary in the schema definition
    import re as _re
    pattern = rf'\b{_re.escape(column)}\b'
    return bool(_re.search(pattern, create_sql))


def _apply_sqlite_compat_migrations(sync_conn) -> None:
    """Apply lightweight additive SQLite migrations for local developer DBs."""
    for table, migrations in _SQLITE_COLUMN_MIGRATIONS.items():
        _validate_identifier(table, "table name")
        if table not in _ALLOWED_MIGRATION_TABLES:
            raise ValueError(f"Table {table!r} not in allowed migration tables")
        if not _sqlite_table_exists(sync_conn, table):
            continue
        for column, ddl in migrations:
            _validate_identifier(column, "column name")
            if _sqlite_has_column(sync_conn, table, column):
                continue
            _DANGEROUS_KW = {"DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE", ";", "--"}
            if any(kw in ddl.upper() for kw in _DANGEROUS_KW):
                raise ValueError(f"Dangerous keyword in DDL: {ddl!r}")
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
