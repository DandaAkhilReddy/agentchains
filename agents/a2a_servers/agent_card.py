"""A2A Agent Card generation — produces .well-known/agent.json compliant cards."""

import json
from typing import Any

# A2A Extension URI for AgentChains chaining metadata
AGENTCHAINS_CHAINING_EXT = "https://agentchains.ai/ext/chaining/v1"


def generate_agent_card(
    name: str,
    description: str,
    url: str,
    skills: list[dict[str, Any]] | None = None,
    capabilities: list[str] | None = None,
    auth_schemes: list[dict[str, str]] | None = None,
    version: str = "0.1.0",
    chaining_params: dict[str, Any] | None = None,
) -> dict:
    """Generate an A2A-compliant agent card.

    The agent card is served at /.well-known/agent.json and describes
    the agent's capabilities, skills, and authentication requirements.

    Args:
        name: Human-readable agent name
        description: What this agent does
        url: Base URL where the agent's A2A server runs
        skills: List of skill definitions with id, name, description
        capabilities: List of supported A2A capabilities
        auth_schemes: Authentication schemes the agent supports
        version: Agent version string

    Returns:
        Dict conforming to the A2A AgentCard schema
    """
    if skills is None:
        skills = []
    if capabilities is None:
        capabilities = ["streaming", "pushNotifications"]
    if auth_schemes is None:
        auth_schemes = [{"scheme": "bearer", "description": "JWT bearer token"}]

    caps_dict: dict[str, Any] = {cap: True for cap in capabilities}

    if chaining_params is not None:
        caps_dict["extensions"] = [
            {
                "uri": AGENTCHAINS_CHAINING_EXT,
                "required": False,
                "description": "AgentChains chaining metadata",
                "params": chaining_params,
            }
        ]

    return {
        "name": name,
        "description": description,
        "url": url,
        "version": version,
        "capabilities": caps_dict,
        "authentication": {
            "schemes": auth_schemes,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": skill.get("id", f"skill-{i}"),
                "name": skill.get("name", f"Skill {i}"),
                "description": skill.get("description", ""),
                "tags": skill.get("tags", []),
                "examples": skill.get("examples", []),
            }
            for i, skill in enumerate(skills)
        ],
    }


def agent_card_from_marketplace(
    agent_data: dict,
    base_url: str,
    chaining_params: dict[str, Any] | None = None,
) -> dict:
    """Generate an agent card from marketplace registration data.

    Args:
        agent_data: Dict from marketplace agent registration (id, name, description, capabilities)
        base_url: URL where the A2A server runs
        chaining_params: Optional AgentChains chaining extension metadata

    Returns:
        A2A AgentCard dict
    """
    capabilities_raw = agent_data.get("capabilities", "[]")
    if isinstance(capabilities_raw, str):
        try:
            caps = json.loads(capabilities_raw)
        except (json.JSONDecodeError, TypeError):
            caps = []
    else:
        caps = capabilities_raw

    skills = [
        {
            "id": f"cap-{i}",
            "name": cap,
            "description": f"Agent capability: {cap}",
            "tags": [cap],
        }
        for i, cap in enumerate(caps)
    ]

    return generate_agent_card(
        name=agent_data.get("name", "Unknown Agent"),
        description=agent_data.get("description", ""),
        url=base_url,
        skills=skills,
        version="0.1.0",
        chaining_params=chaining_params,
    )
