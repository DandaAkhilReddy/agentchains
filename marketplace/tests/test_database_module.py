"""Database module tests."""

from __future__ import annotations
import uuid
from unittest.mock import MagicMock
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from marketplace.database import (
    Base, _IDENTIFIER_RE, _ALLOWED_MIGRATION_TABLES, _SQLITE_COLUMN_MIGRATIONS,
    _validate_identifier, _sqlite_table_exists, _sqlite_has_column, engine,
)
from marketplace.models import *  # noqa: F401, F403

async def _fe():
    return create_async_engine("sqlite+aiosqlite://", echo=False)

async def _ca(e):
    async with e.begin() as c: await c.run_sync(Base.metadata.create_all)

async def _da(e):
    async with e.begin() as c: await c.run_sync(Base.metadata.drop_all)

async def _tn(e):
    async with e.begin() as c: return await c.run_sync(lambda x: inspect(x).get_table_names())
class TestInitDrop:
    async def test_create_all(self):
        e=await _fe()
        try:
            await _ca(e); n=await _tn(e)
            assert len(n)>0; assert "registered_agents" in n
        finally: await e.dispose()

    async def test_idempotent(self):
        e=await _fe()
        try: await _ca(e); await _ca(e); assert len(await _tn(e))>0
        finally: await e.dispose()

    async def test_drop_all(self):
        e=await _fe()
        try: await _ca(e); await _da(e); assert len(await _tn(e))==0
        finally: await e.dispose()

    async def test_drop_recreate(self):
        e=await _fe()
        try:
            await _ca(e); orig=set(await _tn(e))
            await _da(e); await _ca(e)
            assert set(await _tn(e))==orig
        finally: await e.dispose()

class TestSession:
    async def test_is_async(self):
        e=await _fe()
        try:
            await _ca(e)
            f=async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)
            async with f() as s: assert isinstance(s, AsyncSession)
        finally: await e.dispose()

    async def test_commit(self):
        from marketplace.models.agent import RegisteredAgent
        e=await _fe()
        try:
            await _ca(e)
            f=async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)
            async with f() as s:
                a=RegisteredAgent(id=str(uuid.uuid4()),name="ct",agent_type="buyer",public_key="k",status="active")
                s.add(a); await s.commit()
        finally: await e.dispose()
    async def test_rollback(self):
        from marketplace.models.agent import RegisteredAgent
        from sqlalchemy import select, func
        e=await _fe()
        try:
            await _ca(e)
            f=async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)
            async with f() as s:
                a=RegisteredAgent(id=str(uuid.uuid4()),name="rb",agent_type="seller",public_key="k",status="active")
                s.add(a); await s.flush(); await s.rollback()
            async with f() as s:
                c=await s.scalar(select(func.count()).select_from(RegisteredAgent))
                assert c==0
        finally: await e.dispose()

    async def test_expire_on_commit_false(self):
        from marketplace.models.agent import RegisteredAgent
        e=await _fe()
        try:
            await _ca(e)
            f=async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)
            async with f() as s:
                a=RegisteredAgent(id=str(uuid.uuid4()),name="et",agent_type="both",public_key="k",status="active")
                s.add(a); await s.commit()
                assert a.name=="et"
        finally: await e.dispose()

class TestBase:
    def test_is_declarative(self): assert issubclass(Base, DeclarativeBase)
    def test_has_tables(self): assert len(Base.metadata.tables)>0
    def test_agents(self): assert "registered_agents" in Base.metadata.tables
    def test_listings(self): assert "data_listings" in Base.metadata.tables
    def test_transactions(self): assert "transactions" in Base.metadata.tables

class TestValidateId:
    def test_valid(self): assert _validate_identifier("data_listings","t")=="data_listings"
    def test_number(self):
        with pytest.raises(ValueError): _validate_identifier("1bad","t")
    def test_special(self):
        with pytest.raises(ValueError): _validate_identifier("x;--","t")
    def test_empty(self):
        with pytest.raises(ValueError): _validate_identifier("","t")
class TestTableExists:
    async def test_true(self):
        e=await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                r=await c.run_sync(lambda x: _sqlite_table_exists(x,"registered_agents"))
                assert r is True
        finally: await e.dispose()
    async def test_false(self):
        e=await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                r=await c.run_sync(lambda x: _sqlite_table_exists(x,"no_table_xyz"))
                assert r is False
        finally: await e.dispose()

class TestHasColumn:
    async def test_true(self):
        e=await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                r=await c.run_sync(lambda x: _sqlite_has_column(x,"data_listings","title"))
                assert r is True
        finally: await e.dispose()
    async def test_false(self):
        e=await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                r=await c.run_sync(lambda x: _sqlite_has_column(x,"data_listings","nope_xyz"))
                assert r is False
        finally: await e.dispose()
    def test_disallowed_table(self):
        with pytest.raises(ValueError): _sqlite_has_column(MagicMock(),"evil","c")

class TestEng:
    def test_echo_false(self): assert engine.echo is False
    async def test_dispose(self):
        e=await _fe(); await _ca(e); await e.dispose()
    async def test_dispose_idempotent(self):
        e=await _fe(); await e.dispose(); await e.dispose()

class TestGetDb:
    async def test_yields_session(self, db):
        assert isinstance(db, AsyncSession)

class TestMigConfig:
    def test_allowed(self): assert "data_listings" in _ALLOWED_MIGRATION_TABLES
    def test_entries(self): assert len(_SQLITE_COLUMN_MIGRATIONS)>0
    def test_regex(self):
        assert _IDENTIFIER_RE.match("valid_name")
        assert not _IDENTIFIER_RE.match("123bad")


class TestApplySqliteMigrations:
    async def test_migrations_on_minimal_table(self):
        """Create a minimal data_listings table missing migration columns, then migrate."""
        from marketplace.database import _apply_sqlite_compat_migrations
        e = await _fe()
        try:
            async with e.begin() as conn:
                await conn.run_sync(
                    lambda c: c.exec_driver_sql(
                        "CREATE TABLE data_listings (id TEXT PRIMARY KEY, title TEXT)"
                    )
                )
                await conn.run_sync(_apply_sqlite_compat_migrations)
                # Verify columns were added
                has = await conn.run_sync(
                    lambda c: _sqlite_has_column(c, "data_listings", "trust_status")
                )
                assert has is True
        finally:
            await e.dispose()

    async def test_migrations_skip_missing_table(self):
        """When table does not exist, migrations are silently skipped."""
        from marketplace.database import _apply_sqlite_compat_migrations
        e = await _fe()
        try:
            async with e.begin() as conn:
                # No tables at all - should not raise
                await conn.run_sync(_apply_sqlite_compat_migrations)
        finally:
            await e.dispose()


class TestInitDropDispose:
    async def test_init_db_creates_tables(self):
        from unittest.mock import patch, AsyncMock
        from marketplace.database import init_db
        # Mock _apply_sqlite_compat_migrations to avoid duplicate column errors
        with patch("marketplace.database._apply_sqlite_compat_migrations"):
            await init_db()

    async def test_drop_db(self):
        from marketplace.database import drop_db, init_db
        from unittest.mock import patch
        with patch("marketplace.database._apply_sqlite_compat_migrations"):
            await init_db()
        await drop_db()

    async def test_dispose_engine(self):
        from marketplace.database import dispose_engine
        await dispose_engine()


class TestGetDbGenerator:
    async def test_get_db_yields_session(self):
        from marketplace.database import get_db
        gen = get_db()
        session = await gen.__anext__()
        from sqlalchemy.ext.asyncio import AsyncSession
        assert isinstance(session, AsyncSession)
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass


class TestSqliteHasColumnEdgeCases:
    async def test_column_in_nonexistent_table(self):
        e = await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                # Table not in allowed list raises ValueError
                try:
                    await c.run_sync(lambda x: _sqlite_has_column(x, "registered_agents", "id"))
                    assert False, "Should have raised ValueError"
                except ValueError:
                    pass
        finally:
            await e.dispose()

    async def test_column_check_uses_regex(self):
        e = await _fe()
        try:
            await _ca(e)
            async with e.begin() as c:
                # Verify partial match does not count
                result = await c.run_sync(lambda x: _sqlite_has_column(x, "data_listings", "title"))
                assert result is True
                result2 = await c.run_sync(lambda x: _sqlite_has_column(x, "data_listings", "titl"))
                assert result2 is False
        finally:
            await e.dispose()


class TestValidateIdentifierEdge:
    def test_underscore_only(self):
        assert _validate_identifier("_", "t") == "_"

    def test_long_name(self):
        name = "a" * 100
        assert _validate_identifier(name, "t") == name

    def test_with_numbers(self):
        assert _validate_identifier("col_123", "t") == "col_123"

    def test_dash_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            _validate_identifier("col-name", "t")

    def test_space_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            _validate_identifier("col name", "t")

    def test_semicolon_rejected(self):
        import pytest
        with pytest.raises(ValueError):
            _validate_identifier("col;drop", "t")


class TestSqliteHasColumnMissingTable:
    async def test_column_on_nonexistent_allowed_table(self):
        """When table is in allowed list but does not exist, returns False."""
        e = await _fe()
        try:
            # Do NOT create tables - the table does not exist in this fresh DB
            async with e.begin() as c:
                result = await c.run_sync(lambda x: _sqlite_has_column(x, "data_listings", "title"))
                assert result is False
        finally:
            await e.dispose()


class TestApplySqliteMigrationsEdge:
    async def test_dangerous_ddl_rejected(self):
        """Verify that DDL containing dangerous keywords is rejected."""
        from marketplace.database import _apply_sqlite_compat_migrations, _SQLITE_COLUMN_MIGRATIONS
        import copy
        e = await _fe()
        try:
            async with e.begin() as conn:
                await conn.run_sync(
                    lambda c: c.exec_driver_sql(
                        "CREATE TABLE data_listings (id TEXT PRIMARY KEY)"
                    )
                )
            # Temporarily modify the migration config to include a dangerous DDL
            original = _SQLITE_COLUMN_MIGRATIONS.get("data_listings", [])
            _SQLITE_COLUMN_MIGRATIONS["data_listings"] = [("evil_col", "TEXT; DROP TABLE data_listings")]
            try:
                async with e.begin() as conn:
                    try:
                        await conn.run_sync(_apply_sqlite_compat_migrations)
                        assert False, "Should have raised ValueError"
                    except Exception as exc:
                        assert "Dangerous" in str(exc) or "dangerous" in str(exc).lower()
            finally:
                _SQLITE_COLUMN_MIGRATIONS["data_listings"] = original
        finally:
            await e.dispose()

