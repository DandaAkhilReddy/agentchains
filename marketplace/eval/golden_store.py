"""Golden Store — save/load golden input/output pairs for regression testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GoldenStore:
    """File-based storage for golden test cases.

    Structure:
        base_path/
            <agent_id>/
                <test_name>.json  -> {"input": {...}, "output": {...}}
    """

    def __init__(self, base_path: str = "data/eval/golden/") -> None:
        self._base = Path(base_path)

    def save(
        self,
        agent_id: str,
        test_name: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
    ) -> Path:
        """Save a golden input/output pair."""
        agent_dir = self._base / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)

        golden = {
            "input": input_data,
            "output": output_data,
        }
        file_path = agent_dir / f"{test_name}.json"
        file_path.write_text(json.dumps(golden, indent=2, default=str))

        logger.info(
            "golden_saved",
            agent_id=agent_id,
            test_name=test_name,
            path=str(file_path),
        )
        return file_path

    def load(self, agent_id: str, test_name: str) -> dict[str, Any] | None:
        """Load a golden input/output pair."""
        file_path = self._base / agent_id / f"{test_name}.json"
        if not file_path.exists():
            return None
        return json.loads(file_path.read_text())

    def list_tests(self, agent_id: str) -> list[str]:
        """List all golden test names for an agent."""
        agent_dir = self._base / agent_id
        if not agent_dir.exists():
            return []
        return [
            p.stem for p in agent_dir.glob("*.json")
        ]

    def load_all(self, agent_id: str) -> list[dict[str, Any]]:
        """Load all golden test cases for an agent."""
        cases: list[dict[str, Any]] = []
        for test_name in self.list_tests(agent_id):
            case = self.load(agent_id, test_name)
            if case:
                cases.append(case)
        return cases
