"""Static regression checks for experimental Windows runtime A/B; no RF measurements."""
from pathlib import Path


def test_windows_runtime_probe_is_fail_closed_and_branch_scoped():
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    probe = workflow.split("\n  windows-qt-runtime-probe:", 1)[1].split(
        "\n  windows-crash-isolation:", 1)[0]
    assert "needs: windows-tests" in probe
    assert "needs.windows-tests.result == 'failure'" in probe
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in probe
    assert 'python-version: ["3.11", "3.12"]' in probe
    assert 'pyside-version: ["6.9.3", "6.11.3"]' in probe
    assert "PT2VHF_TEST_EXIT_MODE: hard" in probe
    assert "scripts/ci_windows_pytest.py $case" in probe
    assert "if ($LASTEXITCODE -ne 0) { $failed = 1 }" in probe
    assert 'if ($failed -ne 0) { throw' in probe
    assert "gh release create" not in probe
    assert "upload-artifact" not in probe


def test_completed_exit_mechanism_probes_are_not_repeated_hourly():
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    for retired in ("windows-exit-probe", "windows-qt-teardown-probe",
                    "windows-exit-mechanism-probe"):
        assert f"\n  {retired}:" not in workflow
    assert "\n  windows-tests:" in workflow
    assert "\n  windows-exe:" in workflow
