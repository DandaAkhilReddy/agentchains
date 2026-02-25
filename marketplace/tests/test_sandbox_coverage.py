"""Tests for uncovered lines in marketplace/core/sandbox.py."""

import pytest
from marketplace.core.sandbox import SandboxManager, SandboxConfig, SandboxState, SandboxSession


@pytest.fixture
def sandbox():
    return SandboxManager(mode='simulated')


class TestSandboxCreate:
    @pytest.mark.asyncio
    async def test_create_session(self, sandbox):
        s = await sandbox.create_session('agent-1', 'action-1')
        assert s.agent_id == 'agent-1'
        assert s.action_id == 'action-1'
        assert s.state == SandboxState.CREATING

    @pytest.mark.asyncio
    async def test_max_concurrent(self, sandbox):
        sandbox._max_concurrent = 2
        await sandbox.create_session('a', 'x')
        await sandbox.create_session('b', 'y')
        with pytest.raises(RuntimeError, match='Maximum concurrent'):
            await sandbox.create_session('c', 'z')


class TestSandboxExecute:
    @pytest.mark.asyncio
    async def test_execute_simulated(self, sandbox):
        s = await sandbox.create_session('agent-1', 'action-1')
        result = await sandbox.execute(s.session_id, 'echo hello')
        assert result['status'] == 'success'
        assert result['simulated'] is True
        assert s.state == SandboxState.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_not_found(self, sandbox):
        with pytest.raises(ValueError, match='not found'):
            await sandbox.execute('nonexistent', 'cmd')

    @pytest.mark.asyncio
    async def test_execute_with_input_data(self, sandbox):
        s = await sandbox.create_session('agent-1', 'action-1')
        result = await sandbox.execute(s.session_id, 'process', {'key': 'val'})
        assert result['input_data'] == {'key': 'val'}

    @pytest.mark.asyncio
    async def test_execute_docker_fallback(self):
        mgr = SandboxManager(mode='docker')
        s = await mgr.create_session('agent-1', 'action-1')
        # Docker not installed, should fallback to simulated
        result = await mgr.execute(s.session_id, 'echo hi')
        assert result['simulated'] is True

    @pytest.mark.asyncio
    async def test_execute_unknown_mode_fallback(self):
        mgr = SandboxManager(mode='azure_aci')
        s = await mgr.create_session('agent-1', 'action-1')
        result = await mgr.execute(s.session_id, 'cmd')
        assert result['simulated'] is True


class TestSandboxDestroy:
    @pytest.mark.asyncio
    async def test_destroy_session(self, sandbox):
        s = await sandbox.create_session('agent-1', 'action-1')
        assert await sandbox.destroy_session(s.session_id) is True
        assert sandbox.get_session(s.session_id) is None

    @pytest.mark.asyncio
    async def test_destroy_nonexistent(self, sandbox):
        assert await sandbox.destroy_session('nope') is False


class TestSandboxQuery:
    @pytest.mark.asyncio
    async def test_get_session(self, sandbox):
        s = await sandbox.create_session('agent-1', 'action-1')
        result = sandbox.get_session(s.session_id)
        assert result.session_id == s.session_id

    @pytest.mark.asyncio
    async def test_list_sessions(self, sandbox):
        await sandbox.create_session('agent-1', 'a1')
        await sandbox.create_session('agent-2', 'a2')
        await sandbox.create_session('agent-1', 'a3')
        assert len(sandbox.list_sessions()) == 3
        assert len(sandbox.list_sessions(agent_id='agent-1')) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, sandbox):
        assert sandbox.list_sessions() == []


class TestSandboxConfig:
    def test_default_config(self):
        c = SandboxConfig()
        assert c.memory_limit_mb == 512
        assert c.network_enabled is False

    @pytest.mark.asyncio
    async def test_custom_config(self, sandbox):
        cfg = SandboxConfig(memory_limit_mb=1024, network_enabled=True, allowed_domains=['example.com'])
        s = await sandbox.create_session('agent-1', 'action-1', config=cfg)
        assert s.config.memory_limit_mb == 1024
        assert s.config.network_enabled is True
