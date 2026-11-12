"""P0 Windows operational Qt soak without SDR hardware.

Runs a *continuous* QApplication event loop with synthetic waterfall frames,
pan signals and double-click tuning. Unlike short shutdown probes, this checks
for crashes while the UI remains active. It does not exercise USB/audio/SDR
drivers and cannot establish the cause of the user's v0.13.3 field crash.

Parent checks the actual subprocess exit status, including native Windows
exceptions occurring after a successful Qt event loop.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]


def child(seconds: int, source_root: Path) -> int:
    sys.path.insert(0, str(source_root))
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
    os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"

    import numpy as np
    from PySide6.QtCore import QObject, QPointF, Qt, QTimer
    from PySide6.QtWidgets import QApplication
    from types import SimpleNamespace
    from pt2vhf.ui.waterfall import SpectrumWaterfall

    class Harness(QObject):
        def __init__(self, app):
            super().__init__(app)
            self.widget = SpectrumWaterfall()
            self.widget.step = 12_500
            self.widget.set_vfo(145_500_000, -6_000, 6_000)
            self.widget.show()
            self.requests = []
            self.widget.centerTuneRequested.connect(self.requests.append)
            self.ticks = 0
            self.clicks = 0
            self.pans = 0
            self.started = time.monotonic()
            self.update_timer = QTimer(self)
            self.update_timer.setInterval(30)
            self.update_timer.timeout.connect(self.tick)
            self.stop_timer = QTimer(self)
            self.stop_timer.setSingleShot(True)
            self.stop_timer.timeout.connect(self.finish)
            self.update_timer.start()
            self.stop_timer.start(seconds * 1000)

        def tick(self):
            try:
                self.ticks += 1
                n = self.ticks
                self.widget.add_line(
                    np.full(512, -90 - n % 12, dtype=np.float32),
                    145_500_000, 200_000,
                )
                if n == 1:
                    self.widget.spec.setXRange(145.43, 145.57, padding=0)
                if n % 17 == 0:
                    self.widget.spec.getViewBox().sigRangeChangedManually.emit(
                        [True, False]
                    )
                    if not self.widget._pan_timer.isActive():
                        raise AssertionError("Pan debounce timer did not start")
                    self.pans += 1
                if n % 13 == 0:
                    frequency = (145_475_000, 145_500_000, 145_525_000)[
                        (n // 13) % 3
                    ]
                    vb = self.widget.wf.getViewBox()
                    point = vb.mapViewToScene(QPointF(frequency / 1e6, 100))
                    if not vb.sceneBoundingRect().contains(point):
                        raise AssertionError("Double-click point outside waterfall")
                    before = len(self.requests)
                    event = SimpleNamespace(
                        button=lambda: Qt.LeftButton,
                        double=lambda: True,
                        scenePos=lambda: point,
                    )
                    self.widget._clicked(event)
                    if len(self.requests) != before + 1:
                        raise AssertionError("Waterfall double-click was not delivered")
                    if abs(self.requests[-1] - frequency) > 1:
                        raise AssertionError("Waterfall tuned the wrong frequency")
                    self.widget.set_vfo(frequency, -6_000, 6_000)
                    self.widget.center_on_vfo()
                    self.clicks += 1
            except Exception:
                traceback.print_exc()
                self.update_timer.stop()
                QApplication.instance().exit(2)

        def finish(self):
            self.update_timer.stop()
            elapsed = time.monotonic() - self.started
            if self.ticks < seconds * 5 or self.clicks < 1 or self.pans < 1:
                print(
                    f"SOAK-INSUFFICIENT ticks={self.ticks} clicks={self.clicks} "
                    f"pans={self.pans} elapsed={elapsed:.1f}",
                    flush=True,
                )
                QApplication.instance().exit(3)
                return
            print(
                f"SOAK-READY ticks={self.ticks} clicks={self.clicks} "
                f"pans={self.pans} elapsed={elapsed:.1f}",
                flush=True,
            )
            self.widget.close()
            QApplication.instance().quit()

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    harness = Harness(app)
    status = app.exec()
    # Do not use os._exit: native interpreter/Qt teardown is part of this probe.
    return status


def parent(seconds: int, repeats: int, timeout: int, source_root: Path) -> int:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONFAULTHANDLER"] = "1"
    env["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
    env["PT2VHF_NO_AUTOCONNECT"] = "1"
    env["PYTHONPATH"] = str(source_root) + os.pathsep + env.get("PYTHONPATH", "")
    failed = 0
    for attempt in range(1, repeats + 1):
        cmd = [
            sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()),
            "--child", "--seconds", str(seconds), "--source-root", str(source_root),
        ]
        try:
            proc = subprocess.run(
                cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", timeout=timeout, check=False,
            )
            marker = re.search(
                r"SOAK-READY ticks=(\d+) clicks=(\d+) pans=(\d+) elapsed=([\d.]+)",
                proc.stdout,
            )
            valid = (
                proc.returncode == 0 and marker is not None
                and int(marker.group(1)) >= seconds * 5
                and int(marker.group(2)) > 0
                and int(marker.group(3)) > 0
                and float(marker.group(4)) >= seconds * 0.90
            )
            code = f"{proc.returncode} (0x{proc.returncode & 0xffffffff:08X})"
            print(
                f"OPERATIONAL-SOAK attempt={attempt}/{repeats} "
                f"duration={seconds}s status={code} valid={valid}\n"
                f"{proc.stdout[-2500:]}",
                flush=True,
            )
        except subprocess.TimeoutExpired:
            valid = False
            print(
                f"OPERATIONAL-SOAK attempt={attempt}/{repeats} TIMEOUT "
                f"after {timeout}s",
                flush=True,
            )
        if not valid:
            failed += 1
    print(
        f"OPERATIONAL-SOAK-SUMMARY failures={failed}/{repeats} "
        "(synthetic Qt; SDR hardware and real OTA not exercised)",
        flush=True,
    )
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.seconds < 5 or args.repeats < 1:
        parser.error("seconds must be >=5 and repeats >=1")
    source_root = args.source_root.resolve()
    if not (source_root / "pt2vhf" / "ui" / "waterfall.py").is_file():
        parser.error(f"Invalid source root: {source_root}")
    if args.child:
        return child(args.seconds, source_root)
    return parent(
        args.seconds, args.repeats, args.timeout or args.seconds + 60,
        source_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
