"""P0 diagnostic: detect native Qt/pyqtgraph crashes at process shutdown.

Runs a Qt/pyqtgraph teardown isolation matrix in *separate* child processes,
with ordinary Python shutdown and with os._exit.  Unlike pytest's in-process
summary, the parent checks the actual Windows process exit status.
The matrix separates Qt, GraphicsLayout, ImageItem, SDR waterfall initialization,
full synthetic updates, hidden widget and explicit deferred QObject cleanup. It does not
exercise physical SDR drivers or prove the production crash.
"""
from __future__ import annotations

import argparse
import gc
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def child(scenario: str, exit_mode: str, frames: int, source_root: Path) -> int:
    sys.path.insert(0, str(source_root))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
    os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"

    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if scenario == "bare":
        widget = QWidget()
        widget.show()
        app.processEvents()
        widget.close()
        del widget
    elif scenario in ("graphics", "image"):
        # Isolate pyqtgraph scene creation and ImageItem separately from SDR UI.
        import pyqtgraph as pg
        widget = pg.GraphicsLayoutWidget()
        plot = widget.addPlot()
        if scenario == "image":
            import numpy as np
            image = pg.ImageItem()
            plot.addItem(image)
            for index in range(frames):
                image.setImage(
                    np.full((64, 512), -90 - index % 12, dtype=np.float32),
                    autoLevels=False, levels=(-110, -40),
                )
                if index % 4 == 0:
                    app.processEvents()
        widget.show()
        app.processEvents()
        widget.close()
        del widget
    elif scenario in ("waterfall-empty", "waterfall", "waterfall-deferred",
                      "waterfall-empty-deferred", "waterfall-empty-hidden"):
        import numpy as np
        from pt2vhf.ui.waterfall import SpectrumWaterfall

        widget = SpectrumWaterfall()
        widget.set_vfo(145_500_000, -6_000, 6_000)
        if scenario != "waterfall-empty-hidden":
            widget.show()
        for index in range(0 if scenario.startswith("waterfall-empty") else frames):
            widget.add_line(
                np.full(512, -90 - index % 12, dtype=np.float32),
                145_500_000, 200_000,
            )
            if index % 4 == 0:
                app.processEvents()
        widget.close()
        if scenario in ("waterfall-deferred", "waterfall-empty-deferred"):
            # Diagnostic only: force QObject deferred deletes while Qt lives.
            widget.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
        del widget
    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    app.processEvents()
    gc.collect()
    app.processEvents()
    print(f"CHILD-READY scenario={scenario} exit={exit_mode} frames={frames}", flush=True)
    if exit_mode == "hard":
        # ExitProcess still calls native DLL detach handlers on Windows.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    return 0  # Ordinary Python/Qt interpreter shutdown is also tested.


def parent(repeats: int, frames: int, timeout: int, source_root: Path) -> int:
    failures = []
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONFAULTHANDLER"] = "1"
    env["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
    env["PT2VHF_NO_AUTOCONNECT"] = "1"
    env["PYTHONPATH"] = str(source_root) + os.pathsep + env.get("PYTHONPATH", "")
    for scenario in ("bare", "graphics", "image", "waterfall-empty",
                     "waterfall-empty-hidden", "waterfall-empty-deferred",
                     "waterfall", "waterfall-deferred"):
        for exit_mode in ("normal", "hard"):
            for attempt in range(1, repeats + 1):
                cmd = [
                    sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()),
                    "--child", "--scenario", scenario, "--exit-mode", exit_mode,
                    "--frames", str(frames), "--source-root", str(source_root),
                ]
                try:
                    proc = subprocess.run(
                        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, errors="replace", timeout=timeout, check=False,
                    )
                except subprocess.TimeoutExpired as exc:
                    failures.append(f"{scenario}/{exit_mode} #{attempt}: TIMEOUT ({timeout}s)")
                    print(failures[-1], flush=True)
                    continue
                status = f"{proc.returncode} (0x{proc.returncode & 0xffffffff:08X})"
                print(
                    f"QT-EXIT scenario={scenario} mode={exit_mode} attempt={attempt} "
                    f"status={status}\n{proc.stdout[-4000:]}",
                    flush=True,
                )
                if proc.returncode != 0 or "CHILD-READY" not in proc.stdout:
                    failures.append(f"{scenario}/{exit_mode} #{attempt}: {status}")
    if failures:
        print("NATIVE-EXIT-FAILURES:\n" + "\n".join(failures), flush=True)
        return 1
    print("QT native shutdown subprocess probes passed; hardware SDR untested.", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--scenario", choices=("bare", "graphics", "image", "waterfall-empty",
                                             "waterfall-empty-hidden", "waterfall-empty-deferred",
                                             "waterfall", "waterfall-deferred"), default="bare")
    parser.add_argument("--exit-mode", choices=("normal", "hard"), default="normal")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Repository root whose pt2vhf package is exercised")
    args = parser.parse_args()
    if args.frames < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("frames, repeats and timeout must be positive")
    source_root = args.source_root.resolve()
    if not (source_root / "pt2vhf" / "ui" / "waterfall.py").is_file():
        parser.error(f"Invalid source root: {source_root}")
    if args.child:
        return child(args.scenario, args.exit_mode, args.frames, source_root)
    return parent(args.repeats, args.frames, args.timeout, source_root)


if __name__ == "__main__":
    raise SystemExit(main())
