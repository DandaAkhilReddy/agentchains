"""Stub implementation for the NER Extractor agent.

This agent is a placeholder. Implement ``handle_task`` to add real behaviour.
"""
from __future__ import annotations

import uvicorn

from agents.a2a_servers.server import create_a2a_app

# ---------------------------------------------------------------------------
# Skills declaration
# ---------------------------------------------------------------------------

_SKILLS: list[dict] = [{'id': 'ner-extractor/extract', 'name': 'Extract Entities', 'description': 'Identify and label named entities in the provided text.'}]

# ---------------------------------------------------------------------------
# Task handler
# ---------------------------------------------------------------------------


async def handle_task(skill_id: str, message: str, params: dict) -> dict:
    """Handle an incoming A2A task.

    Args:
        skill_id: Identifier of the requested skill.
        message: Human-readable task description or input text.
        params: Full JSON-RPC params dict from the caller.

    Returns:
        Result dict with at minimum a ``status`` key.
    """
    return {
        "status": "not_implemented",
        "agent": "ner-extractor",
        "message": (
            "Agent 'NER Extractor' is a stub. "
            "Implement handle_task() to add real behaviour."
        ),
        "skill_id": skill_id,
    }


# ---------------------------------------------------------------------------
# A2A application factory
# ---------------------------------------------------------------------------


def create_app():
    """Return a FastAPI app implementing the A2A protocol for this agent."""
    return create_a2a_app(
        name="NER Extractor",
        description="Extracts named entities (people, places, organisations) from text.",
        skills=_SKILLS,
        task_handler=handle_task,
        port=9102,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=9102)
