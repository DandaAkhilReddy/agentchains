"""Boot all four A2A agent servers as subprocess processes and wait for health.

Starts each agent with uvicorn in a separate process, polls the
``/.well-known/agent.json`` endpoint until the server is live (or times out),
then prints a status table. Ctrl+C shuts down all processes cleanly.

Usage:
    python scripts/run_agent_servers.py
"""

from __future__ import annotations

import asyncio
import multiprocessing
import signal
import sys
import time
from typing import NamedTuple

import httpx
import uvicorn

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class AgentSpec(NamedTuple):
    """Specification for one agent server."""

    module: str   # uvicorn app import path
    port: int
    display_name: str


AGENTS: list[AgentSpec] = [
    AgentSpec("agents.web_search_agent.a2a_agent:app",     9001, "Web Search"),
    AgentSpec("agents.sentiment_analyzer.a2a_agent:app",   9002, "Sentiment Analyzer"),
    AgentSpec("agents.doc_summarizer_agent.a2a_agent:app", 9003, "Document Summarizer"),
    AgentSpec("agents.report_generator.a2a_agent:app",     9004, "Report Generator"),
]

HEALTH_TIMEOUT_SECONDS: float = 10.0
HEALTH_POLL_INTERVAL_SECONDS: float = 0.25


# ---------------------------------------------------------------------------
# Process boot
# ---------------------------------------------------------------------------

def _run_uvicorn(module: str, port: int) -> None:
    """Target function for each agent subprocess.

    Args:
        module: Importable app path accepted by uvicorn (e.g. ``pkg.mod:app``).
        port: TCP port to listen on.
    """
    uvicorn.run(
        module,
        host="0.0.0.0",
        port=port,
        log_level="warning",  # keep subprocess output quiet
        access_log=False,
    )


def _start_process(spec: AgentSpec) -> multiprocessing.Process:
    """Spawn a uvicorn process for one agent.

    Args:
        spec: Agent specification (module path, port, display name).

    Returns:
        Started ``multiprocessing.Process`` instance.
    """
    proc = multiprocessing.Process(
        target=_run_uvicorn,
        args=(spec.module, spec.port),
        daemon=True,
        name=f"agent-{spec.port}",
    )
    proc.start()
    return proc


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

async def _wait_for_health(spec: AgentSpec) -> bool:
    """Poll an agent's well-known endpoint until it responds or times out.

    Args:
        spec: Agent to check.

    Returns:
        ``True`` if the agent became healthy within the timeout, else ``False``.
    """
    url = f"http://localhost:{spec.port}/.well-known/agent.json"
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS

    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
                pass
            await asyncio.sleep(HEALTH_POLL_INTERVAL_SECONDS)

    return False


async def _check_all_healthy(specs: list[AgentSpec]) -> dict[int, bool]:
    """Check health for all agents concurrently.

    Args:
        specs: List of agent specifications to check.

    Returns:
        Mapping of port → healthy (bool).
    """
    results = await asyncio.gather(*(_wait_for_health(s) for s in specs))
    return {spec.port: ok for spec, ok in zip(specs, results)}


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _print_table(specs: list[AgentSpec], health: dict[int, bool]) -> None:
    """Print a formatted status table for all agents.

    Args:
        specs: Agent specifications.
        health: Port → health status mapping.
    """
    col_name  = 26
    col_port  = 8
    col_url   = 32
    col_state = 8

    sep = f"+{'-' * col_name}+{'-' * col_port}+{'-' * col_url}+{'-' * col_state}+"
    header = (
        f"| {'Agent':<{col_name - 2}} | {'Port':<{col_port - 2}} "
        f"| {'URL':<{col_url - 2}} | {'Status':<{col_state - 2}} |"
    )

    print(sep)
    print(header)
    print(sep)
    for spec in specs:
        ok      = health.get(spec.port, False)
        status  = "OK" if ok else "FAILED"
        url     = f"http://localhost:{spec.port}"
        print(
            f"| {spec.display_name:<{col_name - 2}} | {spec.port:<{col_port - 2}} "
            f"| {url:<{col_url - 2}} | {status:<{col_state - 2}} |"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Boot all agents, verify health, and block until Ctrl+C."""
    print("Starting A2A agent servers...\n")

    processes: list[tuple[AgentSpec, multiprocessing.Process]] = []

    for spec in AGENTS:
        proc = _start_process(spec)
        processes.append((spec, proc))
        print(f"  [{spec.port}] {spec.display_name} — pid {proc.pid}")

    print()

    # Give all processes a moment to bind their sockets before polling
    time.sleep(0.5)

    health = asyncio.run(_check_all_healthy(AGENTS))

    for spec, _ in processes:
        if not health.get(spec.port, False):
            print(
                f"WARNING: {spec.display_name} (port {spec.port}) "
                f"did not become healthy within {HEALTH_TIMEOUT_SECONDS:.0f}s"
            )

    print()
    _print_table(AGENTS, health)
    print()

    live_count = sum(1 for ok in health.values() if ok)
    print(f"{live_count}/{len(AGENTS)} agents healthy. Press Ctrl+C to stop.\n")

    # Block until the user interrupts
    def _shutdown(signum: int, frame: object) -> None:  # noqa: ANN001
        print("\nShutting down agent servers...")
        for _, proc in processes:
            if proc.is_alive():
                proc.terminate()
        for _, proc in processes:
            proc.join(timeout=3.0)
            if proc.is_alive():
                proc.kill()
        print("All servers stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep the main process alive
    while True:
        time.sleep(1.0)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # needed on Windows
    main()
