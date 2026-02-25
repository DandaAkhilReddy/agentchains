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
