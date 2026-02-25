"""Unit tests for the auto_chain_service module."""

import json

import pytest

from marketplace.services.auto_chain_service import (
    CAPABILITY_FLOW_ORDER,
    CAPABILITY_TAXONOMY,
    compose_chain_from_task,
    extract_capabilities,
    suggest_agents_for_capability,
    validate_chain_compatibility,
    _build_graph,
)


# ---------------------------------------------------------------------------
# Capability extraction tests
# ---------------------------------------------------------------------------


class TestExtractCapabilities:
    def test_single_keyword(self):
        caps = extract_capabilities("I need to search the web for data")
        assert "data" in caps

    def test_multiple_capabilities(self):
        caps = extract_capabilities(
            "Search the web, summarize the results, and generate a report"
        )
        assert "data" in caps
        assert "transform" in caps
        assert "output" in caps

    def test_flow_order_preserved(self):
        caps = extract_capabilities(
            "Generate a report after analyzing and searching"
        )
        # Should be in flow order: data → analysis → output
        for i in range(len(caps) - 1):
            assert CAPABILITY_FLOW_ORDER.index(caps[i]) < CAPABILITY_FLOW_ORDER.index(
                caps[i + 1]
            )

    def test_compliance_keywords(self):
        caps = extract_capabilities("Run a KYC check for GDPR compliance")
        assert "compliance" in caps

    def test_no_match_returns_empty(self):
        caps = extract_capabilities("hello world this is random text")
        assert caps == []

    def test_case_insensitive(self):
        caps = extract_capabilities("SEARCH the web and SUMMARIZE")
        assert "data" in caps
        assert "transform" in caps

    def test_all_capabilities(self):
        caps = extract_capabilities(
            "Search data, translate it, run analytics on results, check compliance, generate report"
        )
        assert len(caps) == 5


# ---------------------------------------------------------------------------
# Graph building tests
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_single_node(self):
        assignments = [{"capability": "data", "agent_id": "agent-1"}]
        graph = _build_graph(assignments)
        assert len(graph["nodes"]) == 1
        node = list(graph["nodes"].values())[0]
        assert node["config"]["agent_id"] == "agent-1"
        assert "depends_on" not in node

    def test_linear_chain(self):
        assignments = [
            {"capability": "data", "agent_id": "a1"},
            {"capability": "transform", "agent_id": "a2"},
            {"capability": "output", "agent_id": "a3"},
        ]
        graph = _build_graph(assignments)
        assert len(graph["nodes"]) == 3

        nodes = list(graph["nodes"].items())
        # First node has no dependencies
        assert "depends_on" not in nodes[0][1]
        # Second depends on first
        assert nodes[1][1]["depends_on"] == [nodes[0][0]]
        # Third depends on second
        assert nodes[2][1]["depends_on"] == [nodes[1][0]]


# ---------------------------------------------------------------------------
# Agent suggestion tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_no_agents(db):
    """No agents registered → empty result."""
    agents = await suggest_agents_for_capability(db, "data")
    assert agents == []


@pytest.mark.asyncio
async def test_suggest_finds_by_capabilities(db, make_agent):
    """Agent with matching capabilities JSON should be found."""
    agent, _ = await make_agent()
    agent.capabilities = json.dumps(["web-search", "scraping"])
    agent.description = "A data fetching agent"
    await db.commit()

    agents = await suggest_agents_for_capability(db, "data")
    assert len(agents) >= 1
    assert agents[0]["agent_id"] == agent.id


@pytest.mark.asyncio
async def test_suggest_finds_by_catalog(db, make_agent, make_catalog_entry):
    """Agent with matching catalog entry should be found."""
    agent, _ = await make_agent()
    await make_catalog_entry(
        agent.id,
        namespace="web_search",
        topic="web-search results",
        description="Performs web search queries",
    )

    agents = await suggest_agents_for_capability(db, "data")
    assert len(agents) >= 1
    ids = [a["agent_id"] for a in agents]
    assert agent.id in ids


@pytest.mark.asyncio
async def test_suggest_ranks_by_reputation(db, make_agent):
    """Agents with higher reputation should rank higher."""
    from marketplace.models.reputation import ReputationScore

    agent_a, _ = await make_agent()
    agent_a.capabilities = json.dumps(["search", "data"])
    await db.commit()

    agent_b, _ = await make_agent()
    agent_b.capabilities = json.dumps(["search", "data"])
    await db.commit()

    # Give agent_b higher reputation
    rep_b = ReputationScore(agent_id=agent_b.id, composite_score=0.95)
    rep_a = ReputationScore(agent_id=agent_a.id, composite_score=0.3)
    db.add(rep_a)
    db.add(rep_b)
    await db.commit()

    agents = await suggest_agents_for_capability(db, "data")
    assert len(agents) >= 2
    assert agents[0]["agent_id"] == agent_b.id


@pytest.mark.asyncio
async def test_suggest_respects_max_price(db, make_agent, make_catalog_entry):
    """max_price filter should exclude expensive agents."""
    agent, _ = await make_agent()
    await make_catalog_entry(
        agent.id,
        namespace="web_search",
        topic="web-search data",
        price_range_min=5.0,
    )

    agents = await suggest_agents_for_capability(db, "data", max_price=1.0)
    ids = [a["agent_id"] for a in agents]
    assert agent.id not in ids


@pytest.mark.asyncio
async def test_suggest_skips_inactive_agents(db, make_agent):
    """Inactive agents should not appear in suggestions."""
    agent, _ = await make_agent()
    agent.capabilities = json.dumps(["search", "data"])
    agent.status = "suspended"
    await db.commit()

    agents = await suggest_agents_for_capability(db, "data")
    ids = [a["agent_id"] for a in agents]
    assert agent.id not in ids


# ---------------------------------------------------------------------------
# Compose chain tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compose_success(db, make_agent):
    """compose_chain_from_task should produce a valid draft with assignments."""
    agent, _ = await make_agent()
    agent.capabilities = json.dumps(["web-search", "data"])
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    draft = await compose_chain_from_task(
        db,
        task_description="Search the web for Python tutorials",
        author_id=agent.id,
    )

    assert draft["status"] == "draft"
    assert "data" in draft["capabilities"]
    assert len(draft["assignments"]) >= 1
    assert draft["assignments"][0]["agent_id"] == agent.id

    # graph_json should be valid
    graph = json.loads(draft["graph_json"])
    assert "nodes" in graph


@pytest.mark.asyncio
async def test_compose_no_capabilities_raises(db, make_agent):
    """Task with unrecognized keywords should raise ValueError."""
    agent, _ = await make_agent()
    with pytest.raises(ValueError, match="Could not identify"):
        await compose_chain_from_task(
            db,
            task_description="hello world random nonsense",
            author_id=agent.id,
        )


@pytest.mark.asyncio
async def test_compose_no_agents_raises(db, make_agent):
    """If no agents match the capability, should raise ValueError."""
    agent, _ = await make_agent()  # No capabilities set
    with pytest.raises(ValueError, match="No active agents found"):
        await compose_chain_from_task(
            db,
            task_description="Search the web for data",
            author_id=agent.id,
        )


@pytest.mark.asyncio
async def test_compose_multi_capability(db, make_agent):
    """Compose with multiple capabilities picks one agent per capability."""
    agent_data, _ = await make_agent()
    agent_data.capabilities = json.dumps(["web-search", "data"])
    agent_data.a2a_endpoint = "http://data:9000"
    await db.commit()

    agent_transform, _ = await make_agent()
    agent_transform.capabilities = json.dumps(["summarization", "transform"])
    agent_transform.a2a_endpoint = "http://transform:9000"
    await db.commit()

    draft = await compose_chain_from_task(
        db,
        task_description="Search data and summarize the results",
        author_id=agent_data.id,
    )

    assert len(draft["capabilities"]) == 2
    assert len(draft["assignments"]) == 2
    assert draft["capabilities"] == ["data", "transform"]


# ---------------------------------------------------------------------------
# Validate chain compatibility tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_healthy_chain(db, make_agent):
    """Validation of a chain with active agents returns valid=True."""
    from marketplace.services.chain_registry_service import publish_chain_template

    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(
        db, name="ValidChain", graph_json=json.dumps(graph), author_id=agent.id
    )

    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    assert len(result["agents"]) == 1
    assert result["agents"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_validate_inactive_agent(db, make_agent):
    """Validation should flag inactive agents."""
    from marketplace.services.chain_registry_service import publish_chain_template

    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(
        db, name="WillFail", graph_json=json.dumps(graph), author_id=agent.id
    )

    # Deactivate agent after template creation
    agent.status = "suspended"
    await db.commit()

    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
    assert any("not active" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_missing_endpoint(db, make_agent):
    """Validation should flag agents without an A2A endpoint."""
    from marketplace.services.chain_registry_service import publish_chain_template

    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()

    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(
        db, name="NoEndpoint", graph_json=json.dumps(graph), author_id=agent.id
    )

    # Remove endpoint after template creation
    agent.a2a_endpoint = ""
    await db.commit()

    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
    assert any("no A2A endpoint" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_not_found(db):
    """Validation of nonexistent template raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await validate_chain_compatibility(db, "nonexistent-id")


# ---------------------------------------------------------------------------
# Additional tests for uncovered lines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggest_agent_with_bad_capabilities_json(db, make_agent):
    agent, _ = await make_agent()
    agent.capabilities = "not-valid-json{"
    agent.description = "search data agent"
    await db.commit()
    agents = await suggest_agents_for_capability(db, "data")
    ids = [a["agent_id"] for a in agents]
    assert agent.id in ids


@pytest.mark.asyncio
async def test_suggest_catalog_inactive_agent_skipped(db, make_agent, make_catalog_entry):
    agent, _ = await make_agent()
    agent.status = "suspended"
    await db.commit()
    await make_catalog_entry(agent.id, namespace="web_search", topic="search data", description="data agent")
    agents = await suggest_agents_for_capability(db, "data")
    ids = [a["agent_id"] for a in agents]
    assert agent.id not in ids


@pytest.mark.asyncio
async def test_suggest_respects_min_quality(db, make_agent, make_catalog_entry):
    agent, _ = await make_agent()
    agent.capabilities = json.dumps(["search", "data"])
    await db.commit()
    agents = await suggest_agents_for_capability(db, "data", min_quality=0.9)
    ids = [a["agent_id"] for a in agents]
    assert agent.id not in ids


@pytest.mark.asyncio
async def test_validate_chain_invalid_graph_json(db, make_agent):
    from marketplace.services.chain_registry_service import publish_chain_template
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(
        db, name="BadJSON", graph_json=json.dumps(graph), author_id=agent.id,
    )
    template.graph_json = "not-valid-json{"
    await db.commit()
    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
    assert any("Invalid graph_json" in e for e in result["errors"])

@pytest.mark.asyncio
async def test_validate_chain_missing_agent_id_node(db, make_agent):
    from marketplace.services.chain_registry_service import publish_chain_template
    import json as _json
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(db, name="NoAID", graph_json=_json.dumps(graph), author_id=agent.id)
    g = _json.loads(template.graph_json)
    g["nodes"]["n1"]["config"] = {}
    template.graph_json = _json.dumps(g)
    await db.commit()
    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
    assert any("missing agent_id" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_chain_agent_not_found(db, make_agent):
    from marketplace.services.chain_registry_service import publish_chain_template
    import json as _json
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(db, name="Gone", graph_json=_json.dumps(graph), author_id=agent.id)
    g = _json.loads(template.graph_json)
    g["nodes"]["n1"]["config"]["agent_id"] = "nonexistent-agent-abc"
    template.graph_json = _json.dumps(g)
    await db.commit()
    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
    assert any("not found" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_validate_chain_cycle_detection(db, make_agent):
    from marketplace.services.chain_registry_service import publish_chain_template
    import json as _json
    agent, _ = await make_agent()
    agent.a2a_endpoint = "http://test:9000"
    await db.commit()
    graph = {"nodes": {"n1": {"type": "agent_call", "config": {"agent_id": agent.id}}}, "edges": []}
    template = await publish_chain_template(db, name="Cyc", graph_json=_json.dumps(graph), author_id=agent.id)
    cyclic = {"nodes": {"a": {"type": "agent_call", "config": {"agent_id": agent.id}, "depends_on": ["b"]}, "b": {"type": "agent_call", "config": {"agent_id": agent.id}, "depends_on": ["a"]}}, "edges": []}
    template.graph_json = _json.dumps(cyclic)
    await db.commit()
    result = await validate_chain_compatibility(db, template.id)
    assert result["valid"] is False
