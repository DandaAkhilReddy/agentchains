---
description: Patterns for AI agent implementations
globs: ["agents/**/*.py", "marketplace/mcp/**/*.py", "marketplace/a2ui/**/*.py"]
---

# Agent Patterns Rules

## Agent Structure
Each agent lives in `agents/<agent_name>/` with:
- `__init__.py` — exports
- `agent.py` — main agent logic
- `config.py` — agent-specific configuration
- `tools.py` — tool definitions (if any)

## A2A Protocol
- Agents communicate via the Agent-to-Agent (A2A) protocol
- Server implementations in `agents/a2a_servers/`
- Use the common utilities from `agents/common/`

## MCP Integration
- MCP server implementation in `marketplace/mcp/`
- Agents can expose tools via MCP for Claude Code integration
- Follow the MCP protocol spec for tool definitions

## A2UI Layer
- Agent-to-UI communication via `marketplace/a2ui/`
- Frontend widgets in `frontend/src/components/a2ui/`
- Use structured message formats for UI rendering

## Rules
- Agents must handle errors gracefully — never crash on bad input
- Log all agent interactions for debugging
- Use async throughout — agents are I/O-heavy
- Keep agent state management explicit (no hidden global state)
- Test agents with mocked external dependencies
