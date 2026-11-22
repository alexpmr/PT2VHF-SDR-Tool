"""Regression gates: experimental IQ branch cannot build installers or publish releases.

These checks inspect CI policy only, not installer functionality or RF validation.
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


def test_installer_requires_main_for_manual_dispatch_and_push():
    # An earlier guard restricted only push to main, allowing manual
    # workflow_dispatch on the experimental branch to build an installer.
    guard = _job_guard("windows-exe")
    assert guard == (
        "if: github.ref == 'refs/heads/main' && "
        "((github.event_name == 'workflow_dispatch' && inputs.build_windows) || "
        "(github.event_name == 'push' && "
        "contains(github.event.head_commit.message, '[build-windows]')))"
    )


def test_publication_requires_main_push_with_explicit_marker():
    # A manual dispatch on main may build an installer but must not publish it.
    # Neither manual dispatch nor push on experimental branches may publish.
    guard = _job_guard("publish")
    assert guard == (
        "if: github.event_name == 'push' && github.ref == 'refs/heads/main' "
        "&& contains(github.event.head_commit.message, '[build-windows]')"
    )
