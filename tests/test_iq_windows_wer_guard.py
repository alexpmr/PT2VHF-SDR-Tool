"""Static safety checks for Windows WER crash triage (not runtime/RF QA)."""
from pathlib import Path


def _windows_test_lane() -> str:
    workflow = (Path(__file__).resolve().parents[1] /
                ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    return workflow.split("\n  windows-tests:", 1)[1].split(
        "\n  windows-crash-isolation:", 1
    )[0]


def test_wer_diagnostics_do_not_publish_crash_dumps():
    lane = _windows_test_lane()
    assert "LocalDumps\\\\python.exe" in lane
    assert "DumpType -PropertyType DWord -Value 1" in lane
    assert "DumpCount -PropertyType DWord -Value 3" in lane
    assert "Join-Path $env:RUNNER_TEMP" in lane
    assert "if: failure()" in lane
    assert "Get-WinEvent" in lane
    assert "Get-FileHash" in lane
    assert "actions/upload-artifact" not in lane
    assert "gh release create" not in lane


def test_windows_test_lane_preserves_native_crash_gate():
    lane = _windows_test_lane()
    assert "python scripts/ci_windows_pytest.py" in lane
    assert "QT_QPA_PLATFORM: offscreen" in lane
    assert "github.ref == 'refs/heads/feature/iq-signal-classifier'" in lane
    assert "WER: no python.exe minidump captured" in lane
