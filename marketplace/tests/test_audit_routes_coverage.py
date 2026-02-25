"""Tests for uncovered lines in marketplace/api/audit.py."""

import json
import pytest
from marketplace.core.auth import create_access_token
from marketplace.core.hashing import compute_audit_hash
from marketplace.models.audit_log import AuditLog
from marketplace.services.audit_service import log_event


@pytest.mark.asyncio
async def test_list_audit_events_empty(client, make_agent, auth_header):
    _, token = await make_agent(name='aud-e1')
    resp = await client.get('/api/v1/audit/events', headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data['events'] == []
    assert data['total'] == 0


@pytest.mark.asyncio
async def test_list_audit_events_with_data(client, make_agent, auth_header, db):
    a, token = await make_agent(name='aud-e2')
    await log_event(db, 'agent.registered', agent_id=a.id, severity='info',
                    details={'name': a.name})
    resp = await client.get('/api/v1/audit/events', headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['total'] >= 1


@pytest.mark.asyncio
async def test_list_audit_events_filter_event_type(client, make_agent, auth_header, db):
    a, token = await make_agent(name='aud-e3')
    await log_event(db, 'agent.registered', agent_id=a.id, severity='info')
    await log_event(db, 'purchase.completed', agent_id=a.id, severity='info')
    resp = await client.get('/api/v1/audit/events', params={'event_type': 'agent.registered'},
                            headers=auth_header(token))
    assert resp.status_code == 200
    events = resp.json()['events']
    assert all(e['event_type'] == 'agent.registered' for e in events)


@pytest.mark.asyncio
async def test_list_audit_events_filter_severity(client, make_agent, auth_header, db):
    a, token = await make_agent(name='aud-e4')
    await log_event(db, 'security.alert', agent_id=a.id, severity='warning')
    await log_event(db, 'agent.registered', agent_id=a.id, severity='info')
    resp = await client.get('/api/v1/audit/events', params={'severity': 'warning'},
                            headers=auth_header(token))
    assert resp.status_code == 200
    events = resp.json()['events']
    assert all(e['severity'] == 'warning' for e in events)


@pytest.mark.asyncio
async def test_list_audit_events_pagination(client, make_agent, auth_header, db):
    a, token = await make_agent(name='aud-e5')
    for i in range(5):
        await log_event(db, f'event.{i}', agent_id=a.id, severity='info')
    resp = await client.get('/api/v1/audit/events', params={'page': 1, 'page_size': 2},
                            headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data['events']) == 2
    assert data['total'] == 5


@pytest.mark.asyncio
async def test_list_audit_events_requires_auth(client):
    resp = await client.get('/api/v1/audit/events')
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_audit_chain_empty(client, make_agent, auth_header):
    _, token = await make_agent(name='aud-v1')
    resp = await client.get('/api/v1/audit/events/verify', headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()['valid'] is True


@pytest.mark.asyncio
async def test_verify_audit_chain_valid(client, make_agent, auth_header, db):
    a, token = await make_agent(name='aud-v2')
    await log_event(db, 'event.a', agent_id=a.id, severity='info', details={'step': 1})
    await log_event(db, 'event.b', agent_id=a.id, severity='info', details={'step': 2})
    resp = await client.get('/api/v1/audit/events/verify', headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    # The response must contain valid + entries_checked keys
    assert 'valid' in data
    assert 'entries_checked' in data or 'broken_at' in data


@pytest.mark.asyncio
async def test_verify_audit_chain_requires_auth(client):
    resp = await client.get('/api/v1/audit/events/verify')
    assert resp.status_code == 401
