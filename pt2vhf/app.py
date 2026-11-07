"""Ponto de entrada da aplicação."""
from __future__ import annotations

import argparse
import logging
import sys


def main():
    ap = argparse.ArgumentParser(description="PT2VHF SDR Tool")
    ap.add_argument("--debug", action="store_true", help="log detalhado")
    ap.add_argument("--sim", action="store_true", help="liga o simulador ao iniciar")
    ap.add_argument("--screenshot", metavar="PNG", help="(teste) salva captura de tela e sai")
    ap.add_argument("--selftest", action="store_true", help="verifica a instalação (DSP, decodificadores, interface) e sai")
    args = ap.parse_args()
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    level = logging.DEBUG if args.debug else logging.INFO
    if sys.stderr is None:  # .exe sem console: log em arquivo
        from .config import config_dir
        config_dir().mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=level, format=fmt, filename=str(config_dir() / "pt2vhf-sdr.log"),
                            encoding="utf-8")
    else:
        logging.basicConfig(level=level, format=fmt)
    if args.selftest:
        sys.exit(selftest())

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PT2VHF")
    w = MainWindow()
    w.show()
    if args.sim or args.screenshot:
        w.rx_panel.source.setCurrentText("Simulador")
        w.rx_panel.start_btn.setChecked(True)
    if args.screenshot:
        def shot():
            w._auto_levels()
            QTimer.singleShot(1500, lambda: (w.grab().save(args.screenshot), app.quit()))
        QTimer.singleShot(int(10_000), shot)
    sys.exit(app.exec())


def selftest() -> int:
    """Autoteste usado no build: cadeia DSP + APRS + assistente + interface, sem hardware."""
    import os
    import tempfile
    import threading
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from . import __version__
    from .dsp.assist import detect_mode
    from .dsp.receiver import Receiver
    from .engine import Engine
    from .sources.sim_sources import SimulatorSource
    ok = True

    log_path = os.path.join(tempfile.gettempdir(), "pt2vhf-sdr-selftest.log")
    out = open(log_path, "w", encoding="utf-8")

    def say(msg):
        print(msg, flush=True)  # no .exe sem console, print não faz nada
        out.write(msg + "\n")
        out.flush()

    def check(name, cond):
        nonlocal ok
        say(f"[{'OK' if cond else 'FALHA'}] {name}")
        ok &= bool(cond)

    say(f"PT2VHF SDR Tool {__version__} — autoteste")
    src = SimulatorSource(1_200_000, 145.5e6, realtime=False)
    e = Engine(None)
    e.source, e.rx = src, Receiver(src.sample_rate)
    e.tune(145.570e6)
    dur = src.block_size / src.sample_rate
    for _ in range(int(7 / dur)):
        e.process_block(src.generate(src.block_size))
    pkts = []
    while not e.events.empty():
        k, d, _ = e.events.get()
        if k == "aprs":
            pkts.append(d)
    check("APRS decodificado", bool(pkts) and pkts[0].source == "PY2SIM-9")
    e.tune(145.650e6)
    got, done = [], threading.Event()
    e.capture_if(1.0, lambda iq, fs: (got.append(detect_mode(iq, fs, 145.65e6)), done.set()))
    for _ in range(40):
        e.process_block(src.generate(src.block_size))
    done.wait(10)
    check("Assistente detecta AM", bool(got) and got[0] is not None and got[0].mode == "AM")
    try:
        from PySide6.QtWidgets import QApplication
        from .ui.main_window import MainWindow
        app = QApplication.instance() or QApplication(sys.argv[:1])
        w = MainWindow()
        w.show()
        app.processEvents()
        w.close()
        check("Interface", True)
    except Exception as ex:  # noqa: BLE001
        check(f"Interface ({ex})", False)
    try:
        from rtlsdr.librtlsdr import librtlsdr
        n = librtlsdr.rtlsdr_get_device_count()
        check(f"Biblioteca RTL-SDR carregada ({n} dispositivo(s))", True)
    except Exception as ex:  # noqa: BLE001
        check(f"Biblioteca RTL-SDR ({ex})", False)
    try:
        import sounddevice
        check(f"Áudio (PortAudio {sounddevice.get_portaudio_version()[1]})", True)
    except Exception as ex:  # noqa: BLE001
        say(f"[AVISO] Áudio indisponível neste ambiente: {ex}")
    say("SELFTEST OK" if ok else "SELFTEST FALHOU")
    out.close()
    return 0 if ok else 1


if __name__ == "__main__":
    main()
