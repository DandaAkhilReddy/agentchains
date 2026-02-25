"""Tests for uncovered lines in marketplace/api/discovery.py."""

import pytest


@pytest.mark.asyncio
async def test_discover_no_filters(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c1')
    await make_listing(a.id, title='D1', price_usdc=1.0)
    await make_listing(a.id, title='D2', price_usdc=2.0)
    resp = await client.get('/api/v1/discover')
    assert resp.status_code == 200
    data = resp.json()
    assert data['total'] == 2
    assert data['page'] == 1


@pytest.mark.asyncio
async def test_discover_filter_category(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c2')
    await make_listing(a.id, category='web_search')
    await make_listing(a.id, category='code_analysis')
    resp = await client.get('/api/v1/discover', params={'category': 'code_analysis'})
    assert resp.status_code == 200
    assert resp.json()['total'] == 1


@pytest.mark.asyncio
async def test_discover_filter_seller_id(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c3a')
    b, _ = await make_agent(name='disc-c3b')
    await make_listing(a.id, title='A1')
    await make_listing(b.id, title='B1')
    resp = await client.get('/api/v1/discover', params={'seller_id': b.id})
    assert resp.status_code == 200
    assert all(r['seller_id'] == b.id for r in resp.json()['results'])


@pytest.mark.asyncio
async def test_discover_filter_price_range(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c4')
    await make_listing(a.id, price_usdc=0.5)
    await make_listing(a.id, price_usdc=5.0)
    await make_listing(a.id, price_usdc=50.0)
    resp = await client.get('/api/v1/discover', params={'min_price': 1.0, 'max_price': 10.0})
    assert resp.status_code == 200
    assert resp.json()['total'] == 1


@pytest.mark.asyncio
async def test_discover_sort_by_quality(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c5')
    await make_listing(a.id, title='Low Q', quality_score=0.3)
    await make_listing(a.id, title='High Q', quality_score=0.95)
    resp = await client.get('/api/v1/discover', params={'sort_by': 'quality'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_discover_pagination(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c6')
    for i in range(5):
        await make_listing(a.id, title=f'P{i}')
    resp = await client.get('/api/v1/discover', params={'page': 2, 'page_size': 2})
    assert resp.status_code == 200
    data = resp.json()
    assert data['page'] == 2
    assert data['page_size'] == 2
    assert data['total'] == 5


@pytest.mark.asyncio
async def test_discover_text_search(client, make_agent, make_listing):
    a, _ = await make_agent(name='disc-c7')
    await make_listing(a.id, title='Python ML Tutorial')
    await make_listing(a.id, title='JavaScript Basics')
    resp = await client.get('/api/v1/discover', params={'q': 'python'})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_discover_empty(client):
    resp = await client.get('/api/v1/discover')
    assert resp.status_code == 200
    assert resp.json()['total'] == 0
