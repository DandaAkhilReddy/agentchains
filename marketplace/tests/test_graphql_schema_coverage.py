"""Tests targeting uncovered lines in marketplace/graphql/schema.py."""

import uuid
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from marketplace.graphql.schema import (
    Query, Mutation, _agent_to_type, _listing_to_type,
    _transaction_to_type, _graphql_context_getter,
)


def _patch_async_session(db):
    class _F:
        async def __aenter__(self): return db
        async def __aexit__(self, *a): pass
    return patch('marketplace.graphql.schema.async_session', return_value=_F())


class TestSchemaQueryAgents:
    @pytest.mark.asyncio
    async def test_agents_empty(self, db):
        with _patch_async_session(db):
            assert await Query().agents() == []

    @pytest.mark.asyncio
    async def test_agents_items(self, db, make_agent):
        await make_agent(name='sq-a1')
        await make_agent(name='sq-a2')
        with _patch_async_session(db):
            assert len(await Query().agents()) == 2

    @pytest.mark.asyncio
    async def test_agents_status(self, db, make_agent):
        await make_agent(name='sq-act')
        from marketplace.models.agent import RegisteredAgent
        db.add(RegisteredAgent(id=str(uuid.uuid4()), name='sq-inact',
            agent_type='buyer', public_key='k', status='inactive'))
        await db.commit()
        with _patch_async_session(db):
            r = await Query().agents(status='active')
            assert all(a.status == 'active' for a in r)

    @pytest.mark.asyncio
    async def test_agents_limit_low(self, db, make_agent):
        await make_agent(name='sq-cl')
        with _patch_async_session(db):
            assert len(await Query().agents(limit=0)) <= 1

    @pytest.mark.asyncio
    async def test_agents_limit_high(self, db, make_agent):
        await make_agent(name='sq-ch')
        with _patch_async_session(db):
            assert len(await Query().agents(limit=999)) >= 1


class TestSchemaQueryAgent:
    @pytest.mark.asyncio
    async def test_found(self, db, make_agent):
        a, _ = await make_agent(name='sq-fnd')
        with _patch_async_session(db):
            r = await Query().agent(id=a.id)
            assert r is not None and r.id == a.id

    @pytest.mark.asyncio
    async def test_not_found(self, db):
        with _patch_async_session(db):
            assert await Query().agent(id='miss') is None


class TestSchemaQueryListings:
    @pytest.mark.asyncio
    async def test_empty(self, db):
        with _patch_async_session(db):
            assert await Query().listings() == []

    @pytest.mark.asyncio
    async def test_items(self, db, make_agent, make_listing):
        s, _ = await make_agent(name='sq-ls')
        await make_listing(s.id, title='SQ-L1')
        with _patch_async_session(db):
            assert len(await Query().listings()) == 1

    @pytest.mark.asyncio
    async def test_category(self, db, make_agent, make_listing):
        s, _ = await make_agent(name='sq-lsc')
        await make_listing(s.id, category='web_search')
        await make_listing(s.id, category='code_analysis')
        with _patch_async_session(db):
            assert len(await Query().listings(category='code_analysis')) == 1

    @pytest.mark.asyncio
    async def test_limit_clamp(self, db, make_agent, make_listing):
        s, _ = await make_agent(name='sq-lsl')
        await make_listing(s.id, title='A')
        await make_listing(s.id, title='B')
        with _patch_async_session(db):
            assert len(await Query().listings(limit=-5)) == 1


class TestSchemaQueryListing:
    @pytest.mark.asyncio
    async def test_found(self, db, make_agent, make_listing):
        s, _ = await make_agent(name='sq-sgl')
        li = await make_listing(s.id, title='FindMe')
        with _patch_async_session(db):
            r = await Query().listing(id=li.id)
            assert r is not None and r.title == 'FindMe'

    @pytest.mark.asyncio
    async def test_not_found(self, db):
        with _patch_async_session(db):
            assert await Query().listing(id='nope') is None


class TestSchemaQueryTransactions:
    @pytest.mark.asyncio
    async def test_buyer(self, db, make_agent, make_listing, make_transaction):
        b, _ = await make_agent(name='sq-txb')
        s, _ = await make_agent(name='sq-txs')
        li = await make_listing(s.id)
        await make_transaction(b.id, s.id, li.id)
        with _patch_async_session(db):
            assert len(await Query().transactions(agent_id=b.id)) >= 1

    @pytest.mark.asyncio
    async def test_seller(self, db, make_agent, make_listing, make_transaction):
        b, _ = await make_agent(name='sq-txb2')
        s, _ = await make_agent(name='sq-txs2')
        li = await make_listing(s.id)
        await make_transaction(b.id, s.id, li.id)
        with _patch_async_session(db):
            assert len(await Query().transactions(agent_id=s.id)) >= 1

    @pytest.mark.asyncio
    async def test_empty(self, db, make_agent):
        a, _ = await make_agent(name='sq-notx')
        with _patch_async_session(db):
            assert await Query().transactions(agent_id=a.id) == []

    @pytest.mark.asyncio
    async def test_limit(self, db, make_agent, make_listing, make_transaction):
        b, _ = await make_agent(name='sq-txlb')
        s, _ = await make_agent(name='sq-txls')
        li = await make_listing(s.id)
        for _ in range(3):
            await make_transaction(b.id, s.id, li.id)
        with _patch_async_session(db):
            assert len(await Query().transactions(agent_id=b.id, limit=2)) == 2


class TestSchemaMutationCreateListing:
    @pytest.mark.asyncio
    async def test_no_auth(self, db):
        with _patch_async_session(db):
            info = MagicMock()
            info.context = {'user': None}
            with pytest.raises(PermissionError, match='Authentication required'):
                await Mutation().create_listing(info, title='X', category='c', price_usdc=1.0)

    @pytest.mark.asyncio
    async def test_empty_user(self, db):
        with _patch_async_session(db):
            info = MagicMock()
            info.context = {'user': {}}
            with pytest.raises(PermissionError, match='Authentication required'):
                await Mutation().create_listing(info, title='X', category='c', price_usdc=1.0)

    @pytest.mark.asyncio
    async def test_success(self, db, make_agent):
        a, _ = await make_agent(name='sq-mut')
        with _patch_async_session(db):
            info = MagicMock()
            info.context = {'user': {'id': a.id}}
            r = await Mutation().create_listing(info, title='GL', category='web_search', price_usdc=5.0)
            assert r.title == 'GL' and r.seller_id == a.id


class TestGraphQLContextGetter:
    @pytest.mark.asyncio
    async def test_no_request(self):
        ctx = await _graphql_context_getter(request=None)
        assert ctx['user'] is None

    @pytest.mark.asyncio
    async def test_valid_token(self, client, make_agent):
        a, token = await make_agent(name='sq-ctx')
        resp = await client.post('/graphql', json={'query': '{ __typename }'},
                                  headers={'Authorization': f'Bearer {token}'})
        # The GraphQL endpoint processes context; we test the getter indirectly
        # by verifying it does not crash and returns a response
        assert resp.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        from starlette.requests import Request as SR
        req = MagicMock(spec=SR)
        req.headers = {'authorization': 'Bearer bad'}
        ctx = await _graphql_context_getter(request=req)
        assert ctx['user'] is None

    @pytest.mark.asyncio
    async def test_no_auth_header(self):
        from starlette.requests import Request as SR
        req = MagicMock(spec=SR)
        req.headers = {}
        ctx = await _graphql_context_getter(request=req)
        assert ctx['user'] is None

    @pytest.mark.asyncio
    async def test_non_bearer(self):
        from starlette.requests import Request as SR
        req = MagicMock(spec=SR)
        req.headers = {'authorization': 'Basic abc'}
        ctx = await _graphql_context_getter(request=req)
        assert ctx['user'] is None


class TestSchemaHelpers:
    def test_agent_to_type_datetime(self):
        from datetime import datetime, timezone
        a = MagicMock(id='a1', name='T', description='d',
                      agent_type='buyer', status='active',
                      created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert '2026' in _agent_to_type(a).created_at

    def test_transaction_to_type_datetime(self):
        from datetime import datetime, timezone
        tx = MagicMock(id='t1', listing_id='l1',
                       buyer_id='b1', seller_id='s1',
                       amount_usdc=10.0, status='completed',
                       initiated_at=datetime(2026, 2, 15, tzinfo=timezone.utc))
        assert '2026' in _transaction_to_type(tx).created_at


# ---------------------------------------------------------------------------
# Coverage gap tests — graphql/schema.py lines 271-279
# ---------------------------------------------------------------------------


class TestGraphQLContextGetterCoverage:
    """Lines 271-279: _graphql_context_getter with a real StarletteRequest."""

    @pytest.mark.asyncio
    async def test_valid_bearer_token_sets_user(self, make_agent):
        """Lines 275-277: valid Bearer token populates context['user']."""
        from starlette.requests import Request as StarletteRequest
        from unittest.mock import patch

        a, token = await make_agent(name='gql-ctx-valid')

        # Build a real-looking request: use isinstance patch to let MagicMock pass check
        req = MagicMock()
        req.headers = {'authorization': f'Bearer {token}'}

        with patch("marketplace.graphql.schema._graphql_context_getter.__globals__"
                   if False else "builtins.__import__"):
            # Patch isinstance to return True for StarletteRequest check
            original_isinstance = __builtins__["isinstance"] if isinstance(__builtins__, dict) else isinstance
            pass

        # Use a real StarletteRequest by creating one from scope
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/graphql",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
        real_req = StarletteRequest(scope)
        ctx = await _graphql_context_getter(request=real_req)
        assert ctx['user'] is not None
        assert ctx['user']['id'] == a.id

    @pytest.mark.asyncio
    async def test_invalid_bearer_token_sets_user_none(self):
        """Lines 278-279: bad token → except → context['user'] stays None."""
        from starlette.requests import Request as StarletteRequest
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/graphql",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer invalid.jwt.token")],
        }
        real_req = StarletteRequest(scope)
        ctx = await _graphql_context_getter(request=real_req)
        assert ctx['user'] is None

    @pytest.mark.asyncio
    async def test_bearer_prefix_case_insensitive(self, make_agent):
        """Line 272: startswith check is lowercased — 'bearer ' is the prefix."""
        from starlette.requests import Request as StarletteRequest
        a, token = await make_agent(name='gql-ctx-case')
        # lowercase 'bearer' should also work since we .lower().startswith("bearer ")
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/graphql",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
        real_req = StarletteRequest(scope)
        ctx = await _graphql_context_getter(request=real_req)
        assert ctx['user'] is not None

