"""Tests for the A2A agent card chaining extension."""

from agents.a2a_servers.agent_card import (
    AGENTCHAINS_CHAINING_EXT,
    agent_card_from_marketplace,
    generate_agent_card,
)


class TestAgentCardExtension:
    def test_card_without_chaining_params(self):
        card = generate_agent_card(
            name="TestAgent",
            description="A test agent",
            url="http://localhost:9000",
        )
        # Without chaining_params, no extensions key in capabilities
        assert "extensions" not in card["capabilities"]

    def test_card_with_chaining_params(self):
        params = {
            "chainCapabilities": ["analysis", "compliance"],
            "maxConcurrentChains": 5,
            "jurisdictions": ["CH", "IN"],
        }
        card = generate_agent_card(
            name="ChainAgent",
            description="An agent with chaining",
            url="http://localhost:9000",
            chaining_params=params,
        )
        assert "extensions" in card["capabilities"]
        exts = card["capabilities"]["extensions"]
        assert len(exts) == 1
        ext = exts[0]
        assert ext["uri"] == AGENTCHAINS_CHAINING_EXT
        assert ext["required"] is False
        assert ext["params"]["chainCapabilities"] == ["analysis", "compliance"]
        assert ext["params"]["maxConcurrentChains"] == 5

    def test_marketplace_card_with_chaining(self):
        agent_data = {
            "name": "MarketAgent",
            "description": "From marketplace",
            "capabilities": '["search", "summarize"]',
        }
        params = {"chainCapabilities": ["search"]}
        card = agent_card_from_marketplace(
            agent_data,
            base_url="http://localhost:9000",
            chaining_params=params,
        )
        assert "extensions" in card["capabilities"]
        ext = card["capabilities"]["extensions"][0]
        assert ext["uri"] == AGENTCHAINS_CHAINING_EXT
        assert ext["params"]["chainCapabilities"] == ["search"]
