"""Regression gates: experimental IQ branch must never auto-publish a release.

These checks inspect the CI policy, not the Windows installer or RF model.
"""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build.yml"


def _job_guard(section: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    if section == "windows-exe":
        block = text.split("\n  windows-exe:", 1)[1]
    elif section == "publish":
        block = text.split("      - name: Publicar Release GitHub", 1)[1]
    else:
        raise ValueError(section)
    return next(line.strip() for line in block.splitlines() if line.strip().startswith("if:"))


def test_experimental_push_cannot_trigger_windows_installer():
    guard = _job_guard("windows-exe")
    assert "github.event_name == 'workflow_dispatch' && inputs.build_windows" in guard
    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in guard
    assert "contains(github.event.head_commit.message, '[build-windows]')" in guard


def test_experimental_push_cannot_publish_github_release():
    guard = _job_guard("publish")
    assert "github.event_name == 'push' && github.ref == 'refs/heads/main'" in guard
    assert "contains(github.event.head_commit.message, '[build-windows]')" in guard
