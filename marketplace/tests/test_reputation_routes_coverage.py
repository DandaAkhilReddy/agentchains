"""Tests for uncovered lines in marketplace/api/reputation.py."""

import pytest
from marketplace.services.reputation_service import calculate_reputation


@pytest.mark.asyncio
async def test_leaderboard_empty(client):
    resp = await client.get('/api/v1/reputation/leaderboard')
    assert resp.status_code == 200
    assert resp.json()['entries'] == []


@pytest.mark.asyncio
async def test_leaderboard_with_data(client, make_agent, make_listing, make_transaction, db):
    seller, _ = await make_agent(name='rep-s1')
    buyer, _ = await make_agent(name='rep-b1')
    listing = await make_listing(seller.id)
    await make_transaction(buyer.id, seller.id, listing.id)
    await calculate_reputation(db, seller.id)
    resp = await client.get('/api/v1/reputation/leaderboard')
    assert resp.status_code == 200
    entries = resp.json()['entries']
    assert len(entries) >= 1
    assert entries[0]['rank'] == 1


@pytest.mark.asyncio
async def test_leaderboard_limit(client, make_agent, make_listing, make_transaction, db):
    for i in range(3):
        seller, _ = await make_agent(name=f'rep-sl{i}')
        buyer, _ = await make_agent(name=f'rep-bl{i}')
        listing = await make_listing(seller.id)
        await make_transaction(buyer.id, seller.id, listing.id)
        await calculate_reputation(db, seller.id)
    resp = await client.get('/api/v1/reputation/leaderboard', params={'limit': 2})
    assert resp.status_code == 200
    assert len(resp.json()['entries']) <= 2


@pytest.mark.asyncio
async def test_get_reputation_new_agent(client, make_agent):
    a, _ = await make_agent(name='rep-new')
    resp = await client.get(f'/api/v1/reputation/{a.id}')
    assert resp.status_code == 200
    data = resp.json()
    assert data['agent_id'] == a.id
    assert data['total_transactions'] == 0


@pytest.mark.asyncio
async def test_get_reputation_recalculate(client, make_agent, make_listing, make_transaction, db):
    seller, _ = await make_agent(name='rep-rc')
    buyer, _ = await make_agent(name='rep-rcb')
    listing = await make_listing(seller.id)
    await make_transaction(buyer.id, seller.id, listing.id)
    resp = await client.get(f'/api/v1/reputation/{seller.id}', params={'recalculate': True})
    assert resp.status_code == 200
    assert resp.json()['total_transactions'] >= 1


@pytest.mark.asyncio
async def test_get_reputation_nonexistent_agent(client):
    resp = await client.get('/api/v1/reputation/nonexistent-agent-id')
    assert resp.status_code in (404, 200)
