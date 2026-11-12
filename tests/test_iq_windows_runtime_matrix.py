"""Regression guards for retired Windows runtime A/B and active isolation.

The Python 3.11/3.12 × PySide6 6.9.3/6.11.3 matrix reproduced native
access violations in all eight isolated UI cases (Actions #43177095139).
It must not be re-enabled on every push without a new hypothesis.
These are static workflow checks, not RF or Windows runtime validation.
"""
from pathlib import Path


def _workflow() -> str:
    return (Path(__file__).resolve().parents[1] /
            ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")


def test_exhausted_windows_runtime_matrix_is_retired():
    workflow = _workflow()
    assert "\n  windows-qt-runtime-probe:" not in workflow
    assert 'python-version: ["3.11", "3.12"]' not in workflow
    assert 'pyside-version: ["6.9.3", "6.11.3"]' not in workflow


def test_windows_file_probe_remains_fail_closed_and_experimental_only():
    workflow = _workflow()
    probe = workflow.split("\n  windows-file-probe:", 1)[1].split(
        "\n  windows-case-probe:", 1
    )[0]
    assert "needs: windows-tests" in probe
    assert "needs.windows-tests.result == 'failure'" in probe
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in probe
    assert "ci_windows_file_probe --timeout-seconds 180" in probe
    assert "gh release create" not in probe
    assert "upload-artifact" not in probe


def test_completed_exit_mechanism_probes_are_not_repeated():
    workflow = _workflow()
    for retired in ("windows-exit-probe", "windows-qt-teardown-probe",
                    "windows-exit-mechanism-probe", "windows-qt-runtime-probe"):
        assert f"\n  {retired}:" not in workflow
    assert "\n  windows-tests:" in workflow
    assert "\n  windows-exe:" in workflow
