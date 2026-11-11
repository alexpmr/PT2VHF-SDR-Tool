"""Synthetic regression tests for Windows crash diagnostic sharding."""
from types import SimpleNamespace

import pytest

from scripts import ci_windows_crash_shard as shard


def test_collection_parses_only_node_ids_and_normalizes_paths():
    output = "\n".join([
        "tests/test_b.py::test_two",
        r"tests\test_a.py::test_one[param]",
        "tests/test_b.py::test_three",
        "110/343 tests collected (233 deselected)",
        "WARNING: irrelevant",
    ])
    assert shard.collected_test_files(output) == [
        "tests/test_a.py", "tests/test_b.py"
    ]


def test_shards_are_deterministic_and_do_not_overlap():
    files = [f"tests/test_{name}.py" for name in "dcba"]
    left = shard.shard_files(files, 0, 2)
    right = shard.shard_files(files, 1, 2)
    assert left == ["tests/test_a.py", "tests/test_c.py"]
    assert right == ["tests/test_b.py", "tests/test_d.py"]
    assert set(left).isdisjoint(right)
    assert sorted(left + right) == sorted(files)


@pytest.mark.parametrize("index,count", [(-1, 2), (2, 2), (0, 0)])
def test_invalid_shard_fails_closed(index, count):
    with pytest.raises(ValueError):
        shard.shard_files(["tests/test_a.py"], index, count)


def test_shard_invokes_fail_closed_wrapper_and_preserves_status(monkeypatch):
    seen = []

    def fake_run(command, **kwargs):
        seen.append((command, kwargs))
        if "--collect-only" in command:
            return SimpleNamespace(
                returncode=0,
                stdout="tests/test_b.py::test_b\ntests/test_a.py::test_a\n",
                stderr="",
            )
        return SimpleNamespace(returncode=86)

    monkeypatch.setattr(shard.subprocess, "run", fake_run)
    assert shard.main(["--index", "1", "--count", "2"]) == 86
    assert seen[0][0][1:] == [
        "-m", "pytest", "--collect-only", "-q", "-k", "not iq_", "tests"
    ]
    assert seen[1][0][1:] == [
        "scripts/ci_windows_pytest.py", "-k", "not iq_", "tests/test_b.py"
    ]


def test_empty_collection_does_not_run_tests(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="no tests collected", stderr="")

    monkeypatch.setattr(shard.subprocess, "run", fake_run)
    assert shard.main(["--index", "0", "--count", "2"]) == 2
    assert len(calls) == 1
