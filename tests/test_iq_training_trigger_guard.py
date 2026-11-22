"""Guard against accidental expensive IQ synthetic retraining on routine pushes.

This checks workflow trigger policy only; it does not train or validate RF.
"""
from pathlib import Path
import re


WORKFLOW = (Path(__file__).resolve().parents[1] /
            ".github" / "workflows" / "iq-model-export.yml")


def test_expensive_iq_training_requires_explicit_manual_dispatch():
    header = WORKFLOW.read_text(encoding="utf-8").split("\njobs:", 1)[0]
    assert re.search(r"^on:\s*$", header, re.MULTILINE)
    assert re.search(r"^  workflow_dispatch:\s*$", header, re.MULTILINE)
    for event in ("push", "pull_request", "schedule", "workflow_run"):
        assert not re.search(rf"^  {event}:\s*$", header, re.MULTILINE), event


def test_manual_iq_training_keeps_synthetic_scope_and_no_release():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "train-export-validate:" in text
    assert "verify-v4-across-runners:" in text
    assert "Train UNKNOWN-diverse v4 candidate" in text
    assert "gh release create" not in text
    assert "windows-exe:" not in text


def test_bounded_cpu_diagnostic_requires_explicit_dispatch():
    """Hosted runners are not guaranteed AMD/Intel; don't rerun on every push."""
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "iq-cpu-step-diagnostic.yml")
    header = workflow.read_text(encoding="utf-8").split("\njobs:", 1)[0]
    assert re.search(r"^on:\s*$", header, re.MULTILINE)
    assert re.search(r"^  workflow_dispatch:\s*$", header, re.MULTILINE)
    for event in ("push", "pull_request", "schedule", "workflow_run"):
        assert not re.search(rf"^  {event}:\s*$", header, re.MULTILINE), event
