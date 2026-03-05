"""Tests for marketplace.eval.golden_store — GoldenStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketplace.eval.golden_store import GoldenStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path: Path) -> GoldenStore:
    return GoldenStore(base_path=str(tmp_path / "golden"))


# ---------------------------------------------------------------------------
# save and load round-trip
# ---------------------------------------------------------------------------


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    inp = {"query": "hello", "filters": {"max_price": 100}}
    out = {"listings": [{"id": "abc", "price": 50}], "total": 1}

    store.save("agent-1", "test_search", inp, out)
    loaded = store.load("agent-1", "test_search")

    assert loaded is not None
    assert loaded["input"] == inp
    assert loaded["output"] == out


def test_save_creates_directory(tmp_path: Path) -> None:
    store = _store(tmp_path)
    agent_dir = tmp_path / "golden" / "agent-xyz"
    assert not agent_dir.exists()

    store.save("agent-xyz", "my_test", {}, {})

    assert agent_dir.exists()
    assert agent_dir.is_dir()


def test_save_returns_file_path(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = store.save("agent-1", "test_case", {"k": "v"}, {"r": "s"})
    assert isinstance(path, Path)
    assert path.exists()
    assert path.suffix == ".json"


# ---------------------------------------------------------------------------
# load nonexistent
# ---------------------------------------------------------------------------


def test_load_nonexistent_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.load("agent-1", "does_not_exist")
    assert result is None


def test_load_nonexistent_agent_returns_none(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = store.load("ghost-agent", "any_test")
    assert result is None


# ---------------------------------------------------------------------------
# list_tests
# ---------------------------------------------------------------------------


def test_list_tests_empty(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tests = store.list_tests("agent-1")
    assert tests == []


def test_list_tests_multiple(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save("agent-1", "test_a", {}, {"r": "a"})
    store.save("agent-1", "test_b", {}, {"r": "b"})
    store.save("agent-1", "test_c", {}, {"r": "c"})

    tests = store.list_tests("agent-1")

    assert set(tests) == {"test_a", "test_b", "test_c"}
    assert len(tests) == 3


def test_list_tests_filters_non_json(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save("agent-1", "real_test", {}, {})

    # Place a non-JSON file in the same directory
    agent_dir = tmp_path / "golden" / "agent-1"
    (agent_dir / "readme.txt").write_text("not a test")

    tests = store.list_tests("agent-1")
    assert "readme" not in tests
    assert "real_test" in tests


def test_list_tests_separate_agents(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save("agent-1", "t1", {}, {})
    store.save("agent-2", "t2", {}, {})

    assert store.list_tests("agent-1") == ["t1"]
    assert store.list_tests("agent-2") == ["t2"]


# ---------------------------------------------------------------------------
# load_all
# ---------------------------------------------------------------------------


def test_load_all_returns_all(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save("agent-1", "ta", {"a": 1}, {"ra": 1})
    store.save("agent-1", "tb", {"b": 2}, {"rb": 2})

    cases = store.load_all("agent-1")

    assert len(cases) == 2
    inputs = {c["input"].get("a") or c["input"].get("b") for c in cases}
    assert inputs == {1, 2}


def test_load_all_empty_agent_returns_empty_list(tmp_path: Path) -> None:
    store = _store(tmp_path)
    cases = store.load_all("no-such-agent")
    assert cases == []


# ---------------------------------------------------------------------------
# overwrite
# ---------------------------------------------------------------------------


def test_save_overwrites_existing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save("agent-1", "my_test", {"v": 1}, {"r": "first"})
    store.save("agent-1", "my_test", {"v": 2}, {"r": "second"})

    loaded = store.load("agent-1", "my_test")
    assert loaded is not None
    assert loaded["output"]["r"] == "second"
    assert loaded["input"]["v"] == 2


# ---------------------------------------------------------------------------
# Complex data
# ---------------------------------------------------------------------------


def test_save_complex_data(tmp_path: Path) -> None:
    store = _store(tmp_path)
    inp = {
        "nested": {"deep": {"value": [1, 2, 3]}},
        "unicode": "caf\u00e9 \u4e2d\u6587",
        "bool": True,
        "null": None,
    }
    out = {"results": [{"id": i, "score": i / 10} for i in range(5)]}

    store.save("agent-1", "complex", inp, out)
    loaded = store.load("agent-1", "complex")

    assert loaded is not None
    assert loaded["input"]["nested"]["deep"]["value"] == [1, 2, 3]
    assert loaded["input"]["unicode"] == "caf\u00e9 \u4e2d\u6587"
    assert loaded["output"]["results"][4]["id"] == 4


# ---------------------------------------------------------------------------
# Corrupted file
# ---------------------------------------------------------------------------


def test_load_corrupted_file_raises(tmp_path: Path) -> None:
    store = _store(tmp_path)
    # Manually create a corrupted JSON file
    agent_dir = tmp_path / "golden" / "agent-1"
    agent_dir.mkdir(parents=True)
    (agent_dir / "broken.json").write_text("{not valid json!!!}")

    with pytest.raises(json.JSONDecodeError):
        store.load("agent-1", "broken")


# ---------------------------------------------------------------------------
# Special characters in test name
# ---------------------------------------------------------------------------


def test_save_special_characters_in_test_name(tmp_path: Path) -> None:
    """Test names with hyphens and underscores should work fine."""
    store = _store(tmp_path)
    store.save("agent-1", "test-case_v2-final", {"k": "v"}, {"r": "ok"})

    loaded = store.load("agent-1", "test-case_v2-final")
    assert loaded is not None
    assert loaded["input"]["k"] == "v"
