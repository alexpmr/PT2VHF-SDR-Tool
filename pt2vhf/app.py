"""Ponto de entrada da aplicação."""
from __future__ import annotations

import argparse
import logging
import os
import sys


def main():
    ap = argparse.ArgumentParser(description="PT2VHF SDR Tool")
    ap.add_argument("--debug", action="store_true", help="log detalhado")
    ap.add_argument("--sim", action="store_true", help="liga o simulador ao iniciar")
    ap.add_argument("--screenshot", metavar="PNG", help="(teste) salva captura de tela e sai")
    ap.add_argument("--selftest", action="store_true", help="verifica a instalação (DSP, decodificadores, interface) e sai")
    ap.add_argument("--ota-helper-qa", action="store_true", help=argparse.SUPPRESS)
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
    if args.ota_helper_qa:
        sys.exit(ota_helper_qa())

    # QA P0: local-only native/Python crash evidence before importing Qt.
    from .crash_diagnostics import enable, mark_qt_quit_requested, mark_qt_loop_return
    enable()

    if sys.platform == "win32":  # o instalador (AppMutex) detecta o programa aberto
        import ctypes
        ctypes.windll.kernel32.CreateMutexW(None, False, "PT2VHF_SDR_Tool_Running")
    if args.screenshot:
        os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
        os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.aboutToQuit.connect(mark_qt_quit_requested)
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
    exit_code = app.exec()
    mark_qt_loop_return(exit_code)
    sys.exit(exit_code)



def ota_helper_qa() -> int:
    """Exercise the bundled PowerShell helper without installing or closing GUI.

    This is intentionally limited to frozen Windows builds, with a dummy .exe
    and the helper's -ProbeOnly switch. The real helper's parser and process
    launch flags are both covered, without touching an installed executable.
    """
    import tempfile
    from pathlib import Path
    from . import updater

    output = Path(tempfile.gettempdir()) / "PT2VHF-SDR-Tool-ota-probe-result.txt"
    try:
        with tempfile.TemporaryDirectory(prefix="pt2vhf_ota_probe_") as root:
            package = Path(root) / "probe-package.exe"
            package.write_bytes(b"probe: never execute or install")
            updater.apply(package, "installer", "qa-only", probe_only=True)
        output.write_text("OTA_HELPER_PROBE=PASS\n", encoding="utf-8")
        return 0
    except Exception as exc:
        output.write_text("OTA_HELPER_PROBE=FAIL: " + str(exc) + "\n", encoding="utf-8")
        return 1


def selftest() -> int:
    """Autoteste usado no build: cadeia DSP + APRS + assistente + interface, sem hardware."""
    import os
    import tempfile
    import threading
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["PT2VHF_NO_STARTUP_DIALOGS"] = "1"
    os.environ["PT2VHF_NO_AUTOCONNECT"] = "1"
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
        from .sources.rtlsdr_source import library_info, list_devices
        info = library_info()
        n = len(list_devices())
        blog = info.get("blog", False)
        check(f"Biblioteca RTL-SDR carregada ({n} dispositivo(s)) — "
              + ("driver RTL-SDR Blog (V4)" if blog else "versão padrão"), not info.get("error"))
        if info.get("error_blog"):
            say(f"[INFO] Driver RTL-SDR Blog: {info['error_blog']}")
        if info.get("error"):
            say(f"[INFO] Biblioteca: {info['error']}")
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            check("Driver RTL-SDR Blog incluído (suporte ao V4)", blog)
            from .sources.rtlsdr_source import load_library
            try:
                load_library("standard")
                check("Biblioteca padrão incluída (recurso se o driver Blog não abrir o dongle)", True)
            except Exception as ex:  # noqa: BLE001
                check(f"Biblioteca padrão ({ex})", False)
            load_library("blog")
            from .sources.rtl_driver import wdi_simple_path
            check("Instalador do driver WinUSB incluído (wdi-simple)", wdi_simple_path() is not None)
            from .updater import helper_script
            check("Auxiliar de atualização incluído", helper_script().is_file())
    except Exception as ex:  # noqa: BLE001
        check(f"Biblioteca RTL-SDR ({ex})", False)
    try:
        import urllib.request
        from .webserver import WebServer
        web = WebServer(lambda: {"ok": 1}, lambda: None, port=0)
        web.port = 0
        web.start()
        port = web._httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=5) as r:
            check("Interface web", r.status == 200)
        web.stop()
    except Exception as ex:  # noqa: BLE001
        check(f"Interface web ({ex})", False)
    try:
        from .sonde_rx import locate_binary, synthetic_pipeline_check
        tools = {n: locate_binary(n) for n in ("fsk_demod", "rs41mod")}
        bundled = all(origin == "embarcado" and path for path, origin in tools.values())
        if getattr(sys, "frozen", False):
            check("Decodificadores RS41 embarcados (fsk_demod, rs41mod)", bundled)
        if all(path for path, _ in tools.values()):
            frames = synthetic_pipeline_check(tools["fsk_demod"][0], tools["rs41mod"][0])
            check(f"Pipeline RS41 sintético IQ->fsk_demod->rs41mod ({len(frames)} quadro(s) JSON)",
                  len(frames) >= 2 and all(f.get("id") == "T1234567" for f in frames))
        else:
            say("[INFO] Decodificadores RS41 ausentes neste ambiente (execução pelo código-fonte)")
    except Exception as ex:  # noqa: BLE001
        check(f"Decodificadores RS41 ({ex})", False)
    try:
        from .decoders.modes import ADSBDecoder, ModeSDemodulator, synth_adsb_iq
        vectors = [bytes.fromhex(h) for h in ("8D4840D6202CC371C32CE0576098",
                                               "8D40621D58C386435CC412692AD6",
                                               "8D40621D58C382D690C8AC2863A7")]
        demod, dec = ModeSDemodulator(2_400_000), ADSBDecoder()
        got = demod.process(synth_adsb_iq(vectors, 2_400_000, snr_db=20, freq_offset_hz=50e3))
        for i, msg in enumerate(got):
            dec.ingest(msg, 100.0 + i)
        plane = dec.aircraft.get("40621D", {})
        check(f"ADS-B nativo sintético ({len(got)}/3 quadros Mode S)",
              len(got) == 3 and abs(plane.get("lat", 0) - 52.2572) < 1e-3
              and dec.aircraft.get("4840D6", {}).get("flight") == "KLM1023")
    except Exception as ex:  # noqa: BLE001
        check(f"ADS-B nativo ({ex})", False)
    try:
        from .decoders.acars import AcarsDemodulator, build_block, synth_acars_audio
        demod = AcarsDemodulator()
        msgs = demod.process(synth_acars_audio([build_block(text="M01APT2VHFAUTOTESTE")]))
        msgs += demod.flush()
        check(f"ACARS nativo sintético ({len(msgs)} bloco(s) com CRC)",
              len(msgs) == 1 and msgs[0].get("text") == "AUTOTESTE")
    except Exception as ex:  # noqa: BLE001
        check(f"ACARS nativo ({ex})", False)
    try:
        from .ais_rx import find_ais_catcher, synthetic_ais_check
        path, origin = find_ais_catcher()
        if getattr(sys, "frozen", False):
            check("AIS-catcher embarcado", bool(path) and origin == "embarcado")
        if path:
            ships = synthetic_ais_check(path)
            check(f"Pipeline AIS sintético IQ->rtl_tcp local->AIS-catcher ({len(ships)}/3 navios)",
                  len(ships) == 3)
        else:
            say("[INFO] AIS-catcher ausente neste ambiente (execução pelo código-fonte)")
    except Exception as ex:  # noqa: BLE001
        check(f"AIS-catcher ({ex})", False)
    try:
        from pyrnnoise import RNNoise
        import numpy as np
        den = RNNoise(sample_rate=48000)
        result = list(den.denoise_chunk(np.zeros((1, 960), dtype=np.int16)))
        check("IA neural RNNoise local empacotada (48k / 480)", (
            len(result) == 2 and
            all(np.asarray(item[1]).size == 480 for item in result)))
    except Exception as ex:  # noqa: BLE001
        check(f"RNNoise empacotado ({ex})", False)
    try:
        import ctranslate2
        import faster_whisper
        from faster_whisper.utils import download_model
        check("Transcrição faster-whisper e CTranslate2 incluídos", bool(download_model))
        say("[INFO] Modelos Whisper são baixados exclusivamente por solicitação do usuário.")
    except Exception as ex:  # noqa: BLE001
        check(f"Whisper/CTranslate2 empacotados ({ex})", False)
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
