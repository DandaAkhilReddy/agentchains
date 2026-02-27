"""Scaffold generator for stub agents.

Reads AGENT_DEFINITIONS and creates the directory structure and boilerplate
files for every agent that has ``is_stub=True``.  Safe to re-run — existing
files are not overwritten unless ``--force`` is provided.

Usage::

    python -m agents.registry.scaffold
    python -m agents.registry.scaffold --force   # overwrite existing files
    python -m agents.registry.scaffold --dry-run # print what would be created
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agents.registry.agent_definitions import AGENT_DEFINITIONS, AgentDefinition

# Root of the repository (two levels above this file: agents/registry/ -> agents/ -> repo/)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _REPO_ROOT / "agents"


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------

_INIT_TEMPLATE = '''\
"""Stub agent: {name}."""
from __future__ import annotations

from {module_path}.agent import handle_task, create_app

__all__ = ["handle_task", "create_app"]
'''

_AGENT_TEMPLATE = '''\
"""Stub implementation for the {name} agent.

This agent is a placeholder. Implement ``handle_task`` to add real behaviour.
"""
from __future__ import annotations

import uvicorn

from agents.a2a_servers.server import create_a2a_app

# ---------------------------------------------------------------------------
# Skills declaration
# ---------------------------------------------------------------------------

_SKILLS: list[dict] = {skills!r}

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
    return {{
        "status": "not_implemented",
        "agent": "{slug}",
        "message": (
            "Agent '{name}' is a stub. "
            "Implement handle_task() to add real behaviour."
        ),
        "skill_id": skill_id,
    }}


# ---------------------------------------------------------------------------
# A2A application factory
# ---------------------------------------------------------------------------


def create_app():
    """Return a FastAPI app implementing the A2A protocol for this agent."""
    return create_a2a_app(
        name="{name}",
        description="{description}",
        skills=_SKILLS,
        task_handler=handle_task,
        port={port},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port={port})
'''


# ---------------------------------------------------------------------------
# Scaffold helpers
# ---------------------------------------------------------------------------


def _slug_to_module(slug: str) -> str:
    """Convert a kebab-case slug to a Python module name.

    Args:
        slug: Kebab-case agent slug.

    Returns:
        Underscore-separated module name.

    Example:
        >>> _slug_to_module("sentiment-analyzer")
        'sentiment_analyzer'
    """
    return slug.replace("-", "_")


def _skills_list(agent: AgentDefinition) -> list[dict]:
    """Convert the frozen tuple of skill dicts to a plain list.

    Args:
        agent: The agent definition.

    Returns:
        Mutable list of skill dicts.
    """
    return list(agent.skills)


def scaffold_agent(agent: AgentDefinition, *, force: bool = False, dry_run: bool = False) -> list[Path]:
    """Create the directory and boilerplate files for a single stub agent.

    Args:
        agent: Agent definition to scaffold.
        force: If True, overwrite existing files.
        dry_run: If True, do not write anything — just return the paths that
            would be created.

    Returns:
        List of ``Path`` objects that were (or would be) created.
    """
    module_name = _slug_to_module(agent.slug)
    agent_dir = _AGENTS_DIR / module_name
    module_path = f"agents.{module_name}"

    skills_list = _skills_list(agent)

    files: dict[Path, str] = {
        agent_dir / "__init__.py": _INIT_TEMPLATE.format(
            name=agent.name,
            module_path=module_path,
        ),
        agent_dir / "agent.py": _AGENT_TEMPLATE.format(
            name=agent.name,
            slug=agent.slug,
            description=agent.description,
            skills=skills_list,
            port=agent.port,
        ),
    }

    created: list[Path] = []

    for path, content in files.items():
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or force:
                path.write_text(content, encoding="utf-8")
                created.append(path)
            else:
                # File already exists and force is False — skip silently
                pass
        else:
            created.append(path)

    return created


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the scaffold generator.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success).
    """
    parser = argparse.ArgumentParser(description="Generate stub agent directories.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing agent files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without writing anything.",
    )
    args = parser.parse_args(argv)

    stub_agents = [a for a in AGENT_DEFINITIONS if a.is_stub]
    total_created = 0

    print(f"Scaffolding {len(stub_agents)} stub agents into {_AGENTS_DIR}/")

    for agent in stub_agents:
        created = scaffold_agent(agent, force=args.force, dry_run=args.dry_run)
        for path in created:
            rel = path.relative_to(_REPO_ROOT)
            action = "would create" if args.dry_run else "created"
            print(f"  {action}: {rel}")
        total_created += len(created)

    mode = " (dry run)" if args.dry_run else ""
    print(f"\nDone{mode}: {total_created} files written for {len(stub_agents)} stub agents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
