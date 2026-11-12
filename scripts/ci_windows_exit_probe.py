"""Experimental Windows native-shutdown probe; no RF validation or release build.

Compare Python exit paths with increasingly complex Qt initialization, without
pytest. This distinguishes a bare os._exit failure from Qt object lifecycle or
pytest fixture teardown. A clean result does NOT certify the full Windows suite.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

from scripts.ci_windows_pytest import is_fatal_runtime_output

SCENARIOS = {
    "bare": "pass",
    "qt_import": "from PySide6.QtWidgets import QApplication",
    "qt_widget": (
        "from PySide6.QtWidgets import QApplication, QWidget\n"
        "app = QApplication([])\n"
        "w = QWidget()\n"
        "w.show()\n"
        "app.processEvents()\n"
        "w.close()\n"
        "app.processEvents()"
    ),
    "main_window": (
        "from PySide6.QtWidgets import QApplication\n"
        "from pt2vhf.ui.main_window import MainWindow\n"
        "app = QApplication([])\n"
        "app.setQuitOnLastWindowClosed(False)\n"
        "w = MainWindow()\n"
        "w.close()\n"
        "app.processEvents()"
    ),
}
EXIT_MODES = ("hard", "normal")


def child_code(scenario: str, exit_mode: str) -> str:
    if scenario not in SCENARIOS or exit_mode not in EXIT_MODES:
        raise ValueError("unknown scenario or exit mode")
    end = "os._exit(0)" if exit_mode == "hard" else "raise SystemExit(0)"
    return (
        "import os, sys\n"
        + SCENARIOS[scenario]
        + "\nprint('EXIT-PROBE-READY', flush=True)\n"
        + "sys.stdout.flush()\nsys.stderr.flush()\n"
        + end + "\n"
    )


def probe(timeout_seconds: int = 90) -> int:
    if timeout_seconds < 1:
        raise ValueError("timeout must be positive")
    failures = []
    with tempfile.TemporaryDirectory(prefix="pt2vhf-exit-probe-") as config_dir:
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
                   PT2VHF_NO_STARTUP_DIALOGS="1", PT2VHF_NO_AUTOCONNECT="1",
                   XDG_CONFIG_HOME=config_dir, APPDATA=config_dir)
        for scenario in SCENARIOS:
            for mode in EXIT_MODES:
                cmd = [sys.executable, "-X", "faulthandler", "-c", child_code(scenario, mode)]
                try:
                    run = subprocess.run(cmd, capture_output=True, text=True,
                                         errors="replace", check=False,
                                         timeout=timeout_seconds, env=env)
                    output = run.stdout + "\n" + run.stderr
                    fatal = any(is_fatal_runtime_output(line) for line in output.splitlines())
                    failed = run.returncode != 0 or fatal or "EXIT-PROBE-READY" not in run.stdout
                    print(f"EXIT-PROBE {scenario}/{mode}: exit={run.returncode} fatal={fatal} ready={'EXIT-PROBE-READY' in run.stdout}", flush=True)
                    if failed:
                        failures.append(f"{scenario}/{mode}: exit={run.returncode}, fatal={fatal}")
                        print(output[-5000:], flush=True)
                except subprocess.TimeoutExpired:
                    failures.append(f"{scenario}/{mode}: timeout>{timeout_seconds}s")
                    print(f"EXIT-PROBE {scenario}/{mode}: timeout", flush=True)
    if failures:
        print(f"EXIT-PROBE FAILURES {len(failures)}/{len(SCENARIOS) * len(EXIT_MODES)}:", flush=True)
        for failure in failures:
            print("  " + failure, flush=True)
        return 1
    print("EXIT-PROBE CLEAN (one run only); integrated Windows QA remains blocked", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args(argv)
    return probe(args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
