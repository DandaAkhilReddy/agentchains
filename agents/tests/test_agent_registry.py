"""Tests for the agent definition registry.

Covers:
- Total agent count (exactly 100)
- Slug uniqueness
- Port uniqueness
- Category population (10 categories, each with agents)
- Real-agent flags for the 5 existing agents
- get_agent_by_slug helper
- get_agents_by_category helper
- Skill structure validation
- Scaffold script logic (slug_to_module, scaffold_agent dry-run)
"""
from __future__ import annotations

import pytest

from agents.registry.agent_definitions import (
    AGENT_DEFINITIONS,
    CATEGORIES,
    REAL_AGENTS,
    STUB_AGENTS,
    AgentDefinition,
    get_agent_by_slug,
    get_agents_by_category,
)
from agents.registry.scaffold import _slug_to_module, scaffold_agent

# ---------------------------------------------------------------------------
# Constants expected by the tests
# ---------------------------------------------------------------------------

_REAL_AGENT_SLUGS = {
    "buyer-agent",
    "web-search-agent",
    "code-analyzer-agent",
    "doc-summarizer-agent",
    "knowledge-broker-agent",
}

_EXPECTED_CATEGORY_COUNT = 10
_EXPECTED_TOTAL_AGENTS = 100


# ---------------------------------------------------------------------------
# test_agent_definitions_count
# ---------------------------------------------------------------------------


def test_agent_definitions_count():
    """AGENT_DEFINITIONS must contain exactly 100 agents."""
    assert len(AGENT_DEFINITIONS) == _EXPECTED_TOTAL_AGENTS


# ---------------------------------------------------------------------------
# test_all_slugs_unique
# ---------------------------------------------------------------------------


def test_all_slugs_unique():
    """No two agents may share the same slug."""
    slugs = [a.slug for a in AGENT_DEFINITIONS]
    assert len(slugs) == len(set(slugs)), "Duplicate slugs detected"


# ---------------------------------------------------------------------------
# test_ports_unique
# ---------------------------------------------------------------------------


def test_ports_unique():
    """No two agents may share the same port."""
    ports = [a.port for a in AGENT_DEFINITIONS]
    duplicates = [p for p in ports if ports.count(p) > 1]
    assert not duplicates, f"Duplicate ports: {set(duplicates)}"


# ---------------------------------------------------------------------------
# test_all_categories_populated
# ---------------------------------------------------------------------------


def test_all_categories_populated():
    """Every category in CATEGORIES must have at least one agent."""
    assert len(CATEGORIES) == _EXPECTED_CATEGORY_COUNT
    for category in CATEGORIES:
        agents = get_agents_by_category(category)
        assert agents, f"Category '{category}' has no agents"


# ---------------------------------------------------------------------------
# test_each_category_has_ten_agents
# ---------------------------------------------------------------------------


def test_each_category_has_ten_agents():
    """Each of the 10 categories must contain exactly 10 agents."""
    for category in CATEGORIES:
        agents = get_agents_by_category(category)
        assert len(agents) == 10, (
            f"Category '{category}' has {len(agents)} agents, expected 10"
        )


# ---------------------------------------------------------------------------
# test_real_agents_not_stubs
# ---------------------------------------------------------------------------


def test_real_agents_not_stubs():
    """The 5 existing real agents must have is_stub=False."""
    for slug in _REAL_AGENT_SLUGS:
        agent = get_agent_by_slug(slug)
        assert agent is not None, f"Agent '{slug}' not found in registry"
        assert not agent.is_stub, f"Agent '{slug}' should not be a stub"


# ---------------------------------------------------------------------------
# test_stub_count
# ---------------------------------------------------------------------------


def test_stub_count():
    """Exactly 95 agents should be stubs and 5 should be real."""
    assert len(STUB_AGENTS) == 95
    assert len(REAL_AGENTS) == 5


# ---------------------------------------------------------------------------
# test_get_agent_by_slug
# ---------------------------------------------------------------------------


def test_get_agent_by_slug_returns_correct_agent():
    """get_agent_by_slug should return the matching agent."""
    result = get_agent_by_slug("sentiment-analyzer")
    assert result is not None
    assert result.slug == "sentiment-analyzer"
    assert result.name == "Sentiment Analyzer"


def test_get_agent_by_slug_returns_none_for_unknown():
    """get_agent_by_slug should return None for an unrecognised slug."""
    result = get_agent_by_slug("does-not-exist")
    assert result is None


def test_get_agent_by_slug_works_for_real_agent():
    """get_agent_by_slug should also find the 5 real agents."""
    result = get_agent_by_slug("buyer-agent")
    assert result is not None
    assert result.port == 9001


# ---------------------------------------------------------------------------
# test_get_agents_by_category
# ---------------------------------------------------------------------------


def test_get_agents_by_category_returns_list():
    """get_agents_by_category should return a list."""
    result = get_agents_by_category("Analytics")
    assert isinstance(result, list)


def test_get_agents_by_category_filters_correctly():
    """All returned agents should belong to the requested category."""
    category = "Security"
    agents = get_agents_by_category(category)
    assert agents
    for agent in agents:
        assert agent.category == category


def test_get_agents_by_category_empty_for_unknown():
    """get_agents_by_category should return an empty list for unknown categories."""
    result = get_agents_by_category("NonExistentCategory")
    assert result == []


def test_get_agents_by_category_research_contains_web_search():
    """The Research category must include the real web-search-agent."""
    agents = get_agents_by_category("Research")
    slugs = {a.slug for a in agents}
    assert "web-search-agent" in slugs


# ---------------------------------------------------------------------------
# test_skills_have_required_fields
# ---------------------------------------------------------------------------


def test_skills_have_required_fields():
    """Every skill on every agent must have id, name, and description."""
    for agent in AGENT_DEFINITIONS:
        assert agent.skills, f"Agent '{agent.slug}' has no skills"
        for skill in agent.skills:
            assert "id" in skill, f"Skill missing 'id' on agent '{agent.slug}'"
            assert "name" in skill, f"Skill missing 'name' on agent '{agent.slug}'"
            assert "description" in skill, (
                f"Skill missing 'description' on agent '{agent.slug}'"
            )


def test_skill_ids_contain_slug():
    """Each skill id should start with the agent's slug for namespacing."""
    for agent in AGENT_DEFINITIONS:
        for skill in agent.skills:
            assert skill["id"].startswith(agent.slug), (
                f"Skill id '{skill['id']}' does not start with slug '{agent.slug}'"
            )


# ---------------------------------------------------------------------------
# test_scaffold helpers
# ---------------------------------------------------------------------------


def test_slug_to_module_converts_hyphens():
    """_slug_to_module should replace hyphens with underscores."""
    assert _slug_to_module("sentiment-analyzer") == "sentiment_analyzer"


def test_slug_to_module_no_change_for_no_hyphens():
    """_slug_to_module should be a no-op when there are no hyphens."""
    assert _slug_to_module("analytics") == "analytics"


def test_slug_to_module_multiple_hyphens():
    """_slug_to_module should handle slugs with multiple hyphens."""
    assert _slug_to_module("ab-test-evaluator") == "ab_test_evaluator"


def test_scaffold_agent_dry_run_returns_paths(tmp_path, monkeypatch):
    """scaffold_agent with dry_run=True should return paths without writing."""
    # Point scaffold at a temporary directory so nothing real is written
    import agents.registry.scaffold as scaffold_mod

    monkeypatch.setattr(scaffold_mod, "_AGENTS_DIR", tmp_path)

    sample_agent = next(a for a in AGENT_DEFINITIONS if a.is_stub)
    paths = scaffold_agent(sample_agent, dry_run=True)

    assert len(paths) == 2
    # Nothing should have been written
    assert not any(p.exists() for p in paths)


def test_scaffold_agent_creates_files(tmp_path, monkeypatch):
    """scaffold_agent should write __init__.py and agent.py."""
    import agents.registry.scaffold as scaffold_mod

    monkeypatch.setattr(scaffold_mod, "_AGENTS_DIR", tmp_path)

    sample_agent = next(a for a in AGENT_DEFINITIONS if a.is_stub)
    paths = scaffold_agent(sample_agent)

    for path in paths:
        assert path.exists(), f"Expected file {path} to exist"


def test_scaffold_agent_skips_existing_without_force(tmp_path, monkeypatch):
    """scaffold_agent should not overwrite existing files when force=False."""
    import agents.registry.scaffold as scaffold_mod

    monkeypatch.setattr(scaffold_mod, "_AGENTS_DIR", tmp_path)

    sample_agent = next(a for a in AGENT_DEFINITIONS if a.is_stub)

    # First scaffold — creates files
    first_paths = scaffold_agent(sample_agent)
    assert first_paths  # files were written

    # Write a sentinel into one file
    sentinel = "# SENTINEL DO NOT OVERWRITE"
    first_paths[0].write_text(sentinel, encoding="utf-8")

    # Second scaffold without force — should skip
    second_paths = scaffold_agent(sample_agent, force=False)
    assert second_paths == []  # nothing written

    # Sentinel should still be there
    assert first_paths[0].read_text(encoding="utf-8") == sentinel


def test_scaffold_agent_overwrites_with_force(tmp_path, monkeypatch):
    """scaffold_agent should overwrite existing files when force=True."""
    import agents.registry.scaffold as scaffold_mod

    monkeypatch.setattr(scaffold_mod, "_AGENTS_DIR", tmp_path)

    sample_agent = next(a for a in AGENT_DEFINITIONS if a.is_stub)

    # First scaffold
    first_paths = scaffold_agent(sample_agent)
    sentinel = "# SENTINEL"
    first_paths[0].write_text(sentinel, encoding="utf-8")

    # Second scaffold with force
    scaffold_agent(sample_agent, force=True)

    # Sentinel should be gone
    assert first_paths[0].read_text(encoding="utf-8") != sentinel


# ---------------------------------------------------------------------------
# test_categories constant
# ---------------------------------------------------------------------------


def test_categories_constant_is_sorted():
    """CATEGORIES should be sorted alphabetically."""
    assert CATEGORIES == sorted(CATEGORIES)


def test_categories_contains_all_ten():
    """CATEGORIES must contain the canonical 10 category names."""
    expected = {
        "AI/ML",
        "Analytics",
        "Communication",
        "Content",
        "Data Processing",
        "DevOps",
        "Finance",
        "Research",
        "Security",
        "Utilities",
    }
    assert set(CATEGORIES) == expected


# ---------------------------------------------------------------------------
# test_agent_definition_fields
# ---------------------------------------------------------------------------


def test_agent_definition_is_frozen():
    """AgentDefinition must be a frozen dataclass (immutable)."""
    import dataclasses

    agent = AGENT_DEFINITIONS[0]
    # frozen=True dataclasses raise FrozenInstanceError (subclass of AttributeError)
    with pytest.raises((AttributeError, TypeError)):
        agent.slug = "mutated"  # type: ignore[misc]


def test_all_agents_have_non_empty_description():
    """Every agent must have a non-empty description string."""
    for agent in AGENT_DEFINITIONS:
        assert agent.description.strip(), f"Agent '{agent.slug}' has empty description"


def test_all_agents_have_valid_port():
    """All ports must be positive integers in a valid range."""
    for agent in AGENT_DEFINITIONS:
        assert isinstance(agent.port, int), f"Agent '{agent.slug}' port is not int"
        assert 1 <= agent.port <= 65535, f"Agent '{agent.slug}' port {agent.port} out of range"
