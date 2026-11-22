"""Regression: PowerShell exits before READY on real Windows user systems.

All synthetic tests are offline; the compiled EXE --ota-helper-qa CI job must
also start the exact bundled apply-update.ps1 using genuine WindowsPowerShell.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pt2vhf import updater


def prepare(tmp_path, monkeypatch):
    package = tmp_path / "fake-package.exe"
    package.write_bytes(b"verified-exe-fixture")
    helper = tmp_path / "prebuilt-helper.ps1"
    helper.write_text("param([string]$ReadyFile,[switch]$ProbeOnly)\n", encoding="utf-8")
    monkeypatch.setattr(updater, "helper_script", lambda: helper)
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    # Windows CreateProcess flags are absent on Linux CI; emulate for tests.
    monkeypatch.setattr(updater.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(updater.subprocess, "CREATE_NO_WINDOW", 0x8000000, raising=False)
    monkeypatch.setattr(updater.subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x1000000, raising=False)
    monkeypatch.setattr(updater.subprocess, "DETACHED_PROCESS", 0x8, raising=False)
    return package


def test_no_detached_process_and_redirected_stderr(tmp_path, monkeypatch):
    pkg = prepare(tmp_path, monkeypatch)
    captured = []

    class Running:
        def poll(self):
            return None

    def launch(args, **kwargs):
        captured.append((args, kwargs))
        Path(args[args.index("-ReadyFile") + 1]).write_text("READY", encoding="utf-8")
        return Running()

    monkeypatch.setattr(updater.subprocess, "Popen", launch)
    updater.apply(pkg, "installer", "1.0.3")
    args, kw = captured[0]
    assert "-ProbeOnly" not in args
    assert "-NoProfile" in args
    assert kw["creationflags"] & updater.subprocess.CREATE_NO_WINDOW
    assert not kw["creationflags"] & updater.subprocess.DETACHED_PROCESS
    assert kw["stderr"] == updater.subprocess.STDOUT
    assert kw["stdin"] == updater.subprocess.DEVNULL
    assert "PT2VHF-SDR-Tool-ota-launch.log" in kw["stdout"].name
    assert (tmp_path / "PT2VHF-SDR-Tool-ota-launch.log").exists()


def test_exited_helper_always_leaves_launch_log_and_error_code(tmp_path, monkeypatch):
    pkg = prepare(tmp_path, monkeypatch)

    class Exited:
        def poll(self):
            return 17

    monkeypatch.setattr(updater.subprocess, "Popen", lambda *args, **kw: Exited())
    with pytest.raises(updater.UpdateError, match="código 17") as ex:
        updater.apply(pkg, "installer", "1.0.3")
    assert "PT2VHF-SDR-Tool-ota-launch.log" in str(ex.value)
    text = (tmp_path / "PT2VHF-SDR-Tool-ota-launch.log").read_text(encoding="utf-8")
    assert "mode=installer" in text
    assert "powershell=" in text


def test_fallback_no_breakaway_keeps_console_free_logs(tmp_path, monkeypatch):
    pkg = prepare(tmp_path, monkeypatch)
    attempts = []

    class Running:
        def poll(self):
            return None

    def launch(args, **kw):
        attempts.append(kw)
        if len(attempts) == 1:
            raise OSError("breakaway not permitted")
        Path(args[args.index("-ReadyFile") + 1]).write_text("READY", encoding="utf-8")
        return Running()

    monkeypatch.setattr(updater.subprocess, "Popen", launch)
    updater.apply(pkg, "installer", "1.0.3")
    assert len(attempts) == 2
    assert attempts[0]["creationflags"] & updater.subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert not attempts[1]["creationflags"] & updater.subprocess.CREATE_BREAKAWAY_FROM_JOB
    assert attempts[1]["creationflags"] & updater.subprocess.CREATE_NO_WINDOW


def test_probe_mode_uses_same_powershell_and_waits_for_exit(tmp_path, monkeypatch):
    pkg = prepare(tmp_path, monkeypatch)
    calls = []

    class Probe:
        def poll(self):
            return None

        def wait(self, timeout):
            calls.append(timeout)
            return 0

    def launch(args, **kwargs):
        assert args[-1] == "-ProbeOnly"
        Path(args[args.index("-ReadyFile") + 1]).write_text("READY", encoding="utf-8")
        return Probe()

    monkeypatch.setattr(updater.subprocess, "Popen", launch)
    updater.apply(pkg, "installer", "qa-only", probe_only=True)
    assert calls == [10]


def test_powershell_script_has_probe_guard_before_install():
    src = (Path(__file__).resolve().parents[1] / "scripts" /
           "apply-update.ps1").read_text(encoding="utf-8")
    probe = src.index("if ($ProbeOnly) {")
    installer = src.index("if ($Mode -eq 'Setup')")
    assert probe < installer
    assert "Set-Content -LiteralPath $ReadyFile -Value 'READY'" in src
    assert "exit 0" in src
    assert "PT2VHF-SDR-Tool-ota-helper.log" in src
