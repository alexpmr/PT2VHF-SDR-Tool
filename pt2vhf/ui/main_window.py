"""Janela principal do PT2VHF SDR Tool."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDockWidget, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..audio import AudioOutput
from ..config import Config, config_dir
from ..dsp.demod import dbfs_to_s_units
from ..dsp.receiver import AUDIO_RATE, MODES, passband_for
from ..engine import Engine
from ..memory import MemoryBank, MemoryChannel, band_for
from ..sources.base import SourceError
from ..audio import ActivityRecorder
from ..presets import import_packs
from ..scanner import ScannerConfig, SpectrumScanner
from .lcd import THEMES, LCDDisplay
from .listening import FavoritesBar, PresetDialog, ScannerPanel
from .panels import AudioPanel, DecoderPanel, MemoryPanel, ModePanel, ReceiverPanel
from .waterfall import COLORMAPS, SpectrumWaterfall

log = logging.getLogger(__name__)

STYLE = """
QMainWindow, QWidget { background: #161a20; color: #d8dee6; font-size: 12px; }
QDockWidget::title { background: #232a33; padding: 4px 8px; font-weight: bold; color: #f0b44a; }
QGroupBox { border: 1px solid #2e3742; border-radius: 6px; margin-top: 10px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #f0b44a; }
QPushButton { background: #252d37; border: 1px solid #39444f; border-radius: 4px; padding: 4px 8px; }
QPushButton:hover { background: #2f3945; }
QPushButton:checked { background: #c9871e; color: #120c02; border-color: #f0b44a; font-weight: bold; }
QPushButton#powerButton:checked { background: #1f8a3b; color: white; border-color: #3fd46a; }
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTreeWidget, QTableWidget {
  background: #0f1216; border: 1px solid #2e3742; border-radius: 3px; padding: 2px;
  selection-background-color: #c9871e; selection-color: #120c02; }
QHeaderView::section { background: #232a33; color: #cfd6de; border: 0; padding: 3px; }
QTableWidget, QTreeWidget { alternate-background-color: #141920; gridline-color: #232a33; }
QSlider::groove:horizontal { height: 4px; background: #2e3742; border-radius: 2px; }
QSlider::handle:horizontal { background: #f0b44a; width: 12px; margin: -5px 0; border-radius: 6px; }
QSlider::groove:vertical { width: 4px; background: #2e3742; border-radius: 2px; }
QSlider::handle:vertical { background: #f0b44a; height: 12px; margin: 0 -5px; border-radius: 6px; }
QTabBar::tab { background: #1d232b; padding: 5px 12px; border: 1px solid #2e3742; border-bottom: 0; }
QTabBar::tab:selected { background: #2a323d; color: #f0b44a; }
QStatusBar { background: #10141a; color: #9aa6b2; }
QLabel#bigLabel { font-size: 14px; font-weight: bold; color: #f0b44a; }
QLineEdit#dtmfLine { font: bold 22px Consolas, monospace; color: #f0b44a; }
QToolButton#favButton { background: #252d37; border: 1px solid #39444f; border-radius: 5px;
  padding: 2px 10px; font-size: 11px; min-width: 96px; }
QToolButton#favButton:hover { background: #2f3945; border-color: #f0b44a; }
QToolButton#favButton:checked { background: #c9871e; color: #120c02; font-weight: bold; }
QLabel#favStar { color: #f0b44a; font-size: 20px; padding: 0 4px; }
QLabel#hintLabel { color: #7d8894; font-style: italic; }
QLabel#infoLabel { color: #9aa6b2; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1500, 950)
        self.cfg = Config()
        self.bank = MemoryBank(config_dir() / "memorias.json")
        self.audio = AudioOutput(AUDIO_RATE, self.cfg["audio_device"])
        self.audio.start()
        self.engine = Engine(self.audio)
        self.engine.vfo = self.cfg["vfo_freq"]
        self.engine.fft_size = self.cfg["fft_size"]
        self.engine.wf_speed = self.cfg["wf_speed"]
        self.engine.decoders_enabled = dict(self.cfg["decoders"])

        self.mode = self.cfg["mode"]
        self.low, self.high = passband_for(self.mode, self.cfg["bandwidth"])
        self.step = self.cfg["step"]
        self.vfos = {"A": {"freq": self.cfg["vfo_freq"], "mode": self.mode, "bw": self.cfg["bandwidth"]},
                     "B": {"freq": self.cfg["vfo_b_freq"], "mode": "NFM", "bw": 12000}}
        self.active_vfo = "A"
        self.current_mem: MemoryChannel | None = None
        self.scan = None

        self._build_ui()
        self._wire()
        self._restore_layout()
        self._apply_receiver_settings()
        self._refresh_markers()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.lcd.update)
        self.clock.start(1000)

    # ================================================================== UI
    def _build_ui(self):
        self.setStyleSheet(STYLE)
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks | QMainWindow.AllowNestedDocks)
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(4, 4, 4, 4)
        self.lcd = LCDDisplay()
        self.lcd.set_theme(self.cfg["lcd_theme"])
        cl.addWidget(self.lcd)
        self.fav_bar = FavoritesBar()
        self.fav_bar.refresh(self.bank.channels, self.engine.vfo)
        cl.addWidget(self.fav_bar)
        cl.addLayout(self._build_wf_toolbar())
        self.wf = SpectrumWaterfall()
        self.wf.set_colormap(self.cfg["wf_colormap"])
        self.wf.set_levels(self.cfg["wf_min_db"], self.cfg["wf_max_db"])
        self.wf.avg_alpha = self.cfg["spectrum_avg"]
        cl.addWidget(self.wf, 1)
        self.setCentralWidget(central)

        self.rx_panel = ReceiverPanel(self.cfg)
        self.mode_panel = ModePanel(self.cfg)
        self.audio_panel = AudioPanel(self.cfg)
        self.mem_panel = MemoryPanel(self.bank)
        self.dec_panel = DecoderPanel(self.cfg)
        self.scan_panel = ScannerPanel(self.cfg, self.bank.categories + ["Descobertas"])
        self.sscan: SpectrumScanner | None = None
        self._hits_t = 0.0
        self.docks = {}
        for key, title, w, area in (("rx", "Receptor", self.rx_panel, Qt.LeftDockWidgetArea),
                                    ("mode", "Modo / Filtro", self.mode_panel, Qt.LeftDockWidgetArea),
                                    ("audio", "Áudio / DSP", self.audio_panel, Qt.RightDockWidgetArea),
                                    ("mem", "Memórias / Varredura", self.mem_panel, Qt.BottomDockWidgetArea),
                                    ("scan", "Scanner", self.scan_panel, Qt.BottomDockWidgetArea),
                                    ("dec", "Decodificadores", self.dec_panel, Qt.BottomDockWidgetArea)):
            d = QDockWidget(title, self)
            d.setObjectName(f"dock_{key}")
            d.setWidget(w)
            self.addDockWidget(area, d)
            self.docks[key] = d
        self.tabifyDockWidget(self.docks["rx"], self.docks["mode"])
        self.docks["rx"].raise_()
        self.tabifyDockWidget(self.docks["mem"], self.docks["scan"])
        self.tabifyDockWidget(self.docks["scan"], self.docks["dec"])
        self.docks["mem"].raise_()

        self.status_src = QLabel("Parado")
        self.status_cpu = QLabel("")
        self.status_audio = QLabel("Áudio: OK" if self.audio.available else "Áudio indisponível")
        if not self.audio.available:
            self.status_audio.setToolTip(self.audio.error)
        for w in (self.status_src, self.status_cpu, self.status_audio):
            self.statusBar().addPermanentWidget(w)
        self._build_menu()

    def _build_wf_toolbar(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        self.fft = QComboBox()
        for n in (1024, 2048, 4096, 8192, 16384, 32768):
            self.fft.addItem(f"FFT {n}", n)
        self.fft.setCurrentIndex(max(0, self.fft.findData(self.cfg["fft_size"])))
        self.cmap = QComboBox()
        self.cmap.addItems(list(COLORMAPS))
        self.cmap.setCurrentText(self.cfg["wf_colormap"])
        self.wf_min = QSlider(Qt.Horizontal)
        self.wf_min.setRange(-160, 0)
        self.wf_min.setValue(int(self.cfg["wf_min_db"]))
        self.wf_max = QSlider(Qt.Horizontal)
        self.wf_max.setRange(-150, 20)
        self.wf_max.setValue(int(self.cfg["wf_max_db"]))
        for s in (self.wf_min, self.wf_max):
            s.setMaximumWidth(130)
        self.wf_auto = QPushButton("Auto")
        self.wf_auto.setToolTip("Ajusta piso/teto do waterfall automaticamente (como no KiwiSDR)")
        self.speed = QComboBox()
        for v in (5, 10, 20, 30, 50):
            self.speed.addItem(f"{v} linhas/s", v)
        self.speed.setCurrentIndex(max(0, self.speed.findData(self.cfg["wf_speed"])))
        self.avg = QSlider(Qt.Horizontal)
        self.avg.setRange(0, 95)
        self.avg.setValue(int(self.cfg["spectrum_avg"] * 100))
        self.avg.setMaximumWidth(90)
        self.avg.setToolTip("Média do espectro")
        self.peak = QCheckBox("Pico")
        self.zoom_btns = []
        row.addWidget(self.fft)
        row.addWidget(self.cmap)
        row.addWidget(QLabel("Piso"))
        row.addWidget(self.wf_min)
        row.addWidget(QLabel("Teto"))
        row.addWidget(self.wf_max)
        row.addWidget(self.wf_auto)
        row.addWidget(self.speed)
        row.addWidget(QLabel("Média"))
        row.addWidget(self.avg)
        row.addWidget(self.peak)
        row.addSpacing(10)
        row.addWidget(QLabel("Zoom:"))
        for label, span in (("Total", None), ("500k", 500e3), ("200k", 200e3), ("50k", 50e3), ("10k", 10e3)):
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _=False, s=span: self.wf.reset_zoom() if s is None else self.wf.zoom_to_vfo(s))
            row.addWidget(b)
        row.addStretch(1)
        self.lcd_theme = QComboBox()
        self.lcd_theme.addItems(list(THEMES))
        self.lcd_theme.setCurrentText(self.cfg["lcd_theme"])
        row.addWidget(QLabel("Display:"))
        row.addWidget(self.lcd_theme)
        return row

    def _build_menu(self):
        mb = self.menuBar()
        m = mb.addMenu("&Arquivo")
        a = QAction("Salvar memória atual", self, shortcut=QKeySequence("Ctrl+M"))
        a.triggered.connect(self._save_current_memory)
        m.addAction(a)
        m.addSeparator()
        a = QAction("Sair", self, shortcut=QKeySequence("Ctrl+Q"))
        a.triggered.connect(self.close)
        m.addAction(a)
        v = mb.addMenu("&Exibir")
        for d in self.docks.values():
            v.addAction(d.toggleViewAction())
        v.addSeparator()
        a = QAction("Restaurar layout padrão", self)
        a.triggered.connect(self._reset_layout)
        v.addAction(a)
        h = mb.addMenu("A&juda")
        a = QAction("Atalhos de teclado", self)
        a.triggered.connect(self._show_shortcuts)
        h.addAction(a)
        a = QAction("Sobre", self)
        a.triggered.connect(lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Receptor SDR para radioamadores.<br>"
                            "RTL-SDR, rtl_tcp, SoapySDR, arquivos IQ.<br>Decodificação APRS, DTMF e CTCSS."))
        h.addAction(a)

    # ================================================================== ligações
    def _wire(self):
        lcd, wf, rp, mp, ap, mem, dp = (self.lcd, self.wf, self.rx_panel, self.mode_panel,
                                        self.audio_panel, self.mem_panel, self.dec_panel)
        lcd.freqChanged.connect(self.tune)
        lcd.stepRequested.connect(lambda n: self.tune(self.engine.vfo + n * self.step, snap=True))
        wf.tuneRequested.connect(self.tune)
        wf.passbandChanged.connect(self._set_passband)

        rp.startRequested.connect(self.start_source)
        rp.stopRequested.connect(self.stop_source)
        rp.gainChanged.connect(lambda g: self._src_call("set_gain", g, cfg="gain"))
        rp.ppmChanged.connect(lambda v: self._src_call("set_ppm", v, cfg="ppm"))
        rp.biasTeeChanged.connect(lambda v: self._src_call("set_bias_tee", v, cfg="bias_tee"))
        rp.directSamplingChanged.connect(lambda v: self._src_call("set_direct_sampling", v, cfg="direct_sampling"))

        mp.modeChanged.connect(self.set_mode)
        mp.bandwidthChanged.connect(self.set_bandwidth)
        mp.stepChanged.connect(self.set_step)
        mp.bandSelected.connect(self._goto_band)
        mp.vfoAction.connect(self._vfo_action)
        mp.cwPitchChanged.connect(lambda v: self._rx(lambda rx: (setattr(rx, "cw_pitch", v), rx._build_mode())))
        mp.deemphChanged.connect(self._set_deemph)
        mp.nfmDeemphChanged.connect(lambda v: self._rx(lambda rx: setattr(rx, "nfm_deemph", v)))

        ap.volumeChanged.connect(lambda v: (self._rx(lambda rx: setattr(rx, "volume", v)), self.cfg.__setitem__("volume", v)))
        ap.muteChanged.connect(lambda v: self._rx(lambda rx: setattr(rx, "muted", v)))
        ap.squelchChanged.connect(self._set_squelch)
        ap.squelchAuto.connect(self._auto_squelch)
        ap.agcChanged.connect(self._set_agc)
        ap.manualGainChanged.connect(lambda v: self._rx(lambda rx: setattr(rx.agc, "manual_gain_db", v)))
        ap.nbChanged.connect(self._set_nb)
        ap.nrChanged.connect(self._set_nr)
        ap.notchChanged.connect(self._set_notch)
        ap.ctcssFilterChanged.connect(lambda v: self._rx(lambda rx: setattr(rx.tones, "highpass_enabled", v)))
        ap.lowpassChanged.connect(lambda v: self._rx(lambda rx: rx.tones.set_lowpass(v)))
        ap.eqChanged.connect(self._set_eq)
        ap.recordAudio.connect(self._record_audio)
        ap.recordIQ.connect(self._record_iq)
        ap.deviceChanged.connect(self._audio_device)

        mem.recallRequested.connect(self.recall_memory)
        mem.saveCurrentRequested.connect(self._save_current_memory)
        mem.scanRequested.connect(self._start_scan)
        mem.scanStop.connect(self._stop_scan)
        mem.changed.connect(self._memories_changed)
        mem.presetsRequested.connect(self._open_presets)

        fb = self.fav_bar
        fb.recallRequested.connect(self.recall_memory)
        fb.addCurrentRequested.connect(self._fav_add_current)
        fb.unfavoriteRequested.connect(self._unfavorite)

        sp = self.scan_panel
        sp.startRequested.connect(self._sscan_start)
        sp.stopRequested.connect(self._sscan_stop)
        sp.listenRequested.connect(self._sscan_listen)
        sp.saveRequested.connect(self._sscan_save)
        sp.lockoutRequested.connect(self._sscan_lock)
        sp.clearLockouts.connect(self._sscan_unlock)
        sp.clearHits.connect(self._sscan_clear)
        sp.autoRecordChanged.connect(self._auto_record)
        sp.priorityFromCurrent.connect(lambda: sp.prio.setValue(self.engine.vfo / 1e6))

        dp.enabledChanged.connect(self._set_decoders)
        dp.toneSquelchChanged.connect(self._set_tone_squelch)

        self.fft.currentIndexChanged.connect(lambda _: self._set_engine("fft_size", self.fft.currentData()))
        self.cmap.currentTextChanged.connect(lambda n: (self.wf.set_colormap(n), self.cfg.__setitem__("wf_colormap", n)))
        self.wf_min.valueChanged.connect(self._levels)
        self.wf_max.valueChanged.connect(self._levels)
        self.wf_auto.clicked.connect(self._auto_levels)
        self.speed.currentIndexChanged.connect(lambda _: self._set_engine("wf_speed", self.speed.currentData()))
        self.avg.valueChanged.connect(lambda v: (setattr(self.wf, "avg_alpha", v / 100), self.cfg.__setitem__("spectrum_avg", v / 100)))
        self.peak.toggled.connect(lambda v: (setattr(self.wf, "peak_hold", v), self.wf.clear_peak()))
        self.lcd_theme.currentTextChanged.connect(lambda n: (self.lcd.set_theme(n), self.cfg.__setitem__("lcd_theme", n)))

        # atalhos (estilo KiwiSDR / SDR#)
        for keys, fn in (
            ("Alt+N", lambda: self.set_mode("NFM")), ("Alt+W", lambda: self.set_mode("WFM")),
            ("Alt+A", lambda: self.set_mode("AM")), ("Alt+U", lambda: self.set_mode("USB")),
            ("Alt+L", lambda: self.set_mode("LSB")), ("Alt+C", lambda: self.set_mode("CW")),
            ("Ctrl+Right", lambda: self.tune(self.engine.vfo + self.step, snap=True)),
            ("Ctrl+Left", lambda: self.tune(self.engine.vfo - self.step, snap=True)),
            ("Ctrl+Up", lambda: self.tune(self.engine.vfo + 10 * self.step, snap=True)),
            ("Ctrl+Down", lambda: self.tune(self.engine.vfo - 10 * self.step, snap=True)),
            ("Ctrl+Shift+M", lambda: self.audio_panel.mute.toggle()),
            ("Ctrl+B", lambda: self._vfo_action("swap")),
            ("Ctrl+S", self._auto_squelch),
            ("Ctrl+L", self._auto_levels),
            ("Escape", lambda: (self._stop_scan(), self._sscan_stop())),
        ):
            QShortcut(QKeySequence(keys), self, activated=fn)

    # ================================================================== fonte
    def start_source(self, opts: dict):
        from ..sources.network_sources import RtlTcpSource, SoapySource
        from ..sources.rtlsdr_source import RtlSdrSource
        from ..sources.sim_sources import SimulatorSource, WavIQSource
        name = opts["source"]
        fs = opts["sample_rate"]
        center = self.engine.vfo + fs / 8
        try:
            if name == "Simulador":
                src = SimulatorSource(fs, center)
                src.set_gain(opts["gain"])
            elif name == "RTL-SDR":
                src = RtlSdrSource(fs, center, opts["device_index"], opts["gain"], opts["ppm"])
                src.set_bias_tee(self.cfg["bias_tee"]) if self.cfg["bias_tee"] else None
                if self.cfg["direct_sampling"]:
                    src.set_direct_sampling(self.cfg["direct_sampling"])
            elif name == "rtl_tcp":
                src = RtlTcpSource(fs, center, opts["host"], opts["port"], opts["gain"], opts["ppm"])
                self.cfg["rtl_tcp_host"], self.cfg["rtl_tcp_port"] = opts["host"], opts["port"]
            elif name == "SoapySDR":
                src = SoapySource(fs, center, opts["soapy_args"], opts["gain"], opts["ppm"])
                self.cfg["soapy_args"] = opts["soapy_args"]
            else:
                src = WavIQSource(opts["file"])
                if src.sample_rate % 240_000:
                    src.close()
                    raise SourceError(f"Taxa do arquivo ({src.sample_rate} S/s) precisa ser múltipla de 240 kHz.")
                self.engine.vfo = src.center_freq
        except SourceError as e:
            QMessageBox.warning(self, "Fonte de sinal", str(e))
            self.rx_panel.set_running(False)
            return
        self.cfg.update(source=name, sample_rate=src.sample_rate, gain=opts["gain"], ppm=opts["ppm"])
        self.engine.start(src)
        self._apply_receiver_settings()
        self.rx_panel.set_running(True)
        tuner = getattr(src, "tuner", "")
        self.rx_panel.info.setText(f"{src.name} {tuner} — {src.sample_rate / 1e6:g} MS/s, bloco {src.block_size}")
        self.status_src.setText(f"● {src.name} {src.sample_rate / 1e6:g} MS/s")
        self._update_lcd()

    def stop_source(self):
        self._stop_scan()
        self._sscan_stop()
        self.engine.stop()
        self.rx_panel.set_running(False)
        self.rx_panel.info.setText("Parado")
        self.status_src.setText("Parado")
        self.audio_panel.rec_audio.setChecked(False)
        self.audio_panel.rec_iq.setChecked(False)

    def _src_call(self, method, value, cfg=None):
        if cfg:
            self.cfg[cfg] = value
        src = self.engine.source
        if src is not None:
            try:
                getattr(src, method)(value)
            except Exception as e:  # noqa: BLE001
                self.statusBar().showMessage(f"{method}: {e}", 5000)

    # ================================================================== receptor
    def _rx(self, fn):
        """Executa uma alteração no Receiver de forma segura (thread DSP)."""
        self.engine.call(fn)

    def _set_engine(self, attr, value):
        setattr(self.engine, attr, value)
        self.cfg[attr] = value

    def _apply_receiver_settings(self):
        """Reaplica o estado da interface no Receiver (após ligar uma fonte)."""
        if self.engine.rx is None:
            self._sync_views()
            return
        ap, cfg = self.audio_panel, self.cfg
        mode, low, high = self.mode, self.low, self.high
        tau = cfg["wfm_deemph_us"] * 1e-6

        def apply(rx):
            rx.wfm_deemph_tau = tau
            rx.cw_pitch = float(self.mode_panel.cw_pitch.value())
            rx.mode = mode
            rx.low, rx.high = low, high
            rx._build_mode()
            rx.volume = ap.volume.value() / 100
            rx.muted = ap.mute.isChecked()
            rx.squelch.threshold_db = float(ap.squelch.value())
            rx.agc.enabled = ap.agc.isChecked()
            rx.agc.set_speed(ap.agc_speed.currentText())
            rx.agc.manual_gain_db = float(ap.man_gain.value())
            rx.nb.enabled, rx.nb.threshold = ap.nb.isChecked(), ap.nb_thr.value()
            rx.nr.enabled, rx.nr.strength = ap.nr.isChecked(), ap.nr_str.value() / 10
            rx.notch.enabled = ap.notch.isChecked()
            rx.notch.set_freq(float(ap.notch_f.value()))
            rx.tones.highpass_enabled = ap.ctcss_hp.isChecked()
            rx.tones.set_lowpass(float(ap.lowpass.currentData()))
            rx.nfm_deemph = self.mode_panel.nfm_deemph.isChecked()
            rx.eq.enabled = ap.eq_on.isChecked()
            rx.eq.set_gains(ap.eq_gains())
        self._rx(apply)
        self._sync_views()

    def tune(self, freq: float, snap: bool = False):
        if self.sscan is not None and self.sscan.running and not getattr(self, "_scanner_tuning", False):
            self._sscan_stop()
        if snap and self.step > 0:
            freq = round(freq / self.step) * self.step
        freq = min(max(float(freq), 24_000.0), 1_766_000_000.0)
        self.engine.tune(freq)
        self.vfos[self.active_vfo]["freq"] = freq
        self.cfg["vfo_freq" if self.active_vfo == "A" else "vfo_b_freq"] = freq
        if self.current_mem and abs(self.current_mem.freq - freq) > 1:
            self.current_mem = None
        self._sync_views()

    def set_mode(self, mode: str, width: float | None = None):
        self.mode = mode
        w = width if width is not None else (MODES[mode].high - MODES[mode].low)
        self.low, self.high = passband_for(mode, w)
        low, high = self.low, self.high

        def apply(rx):
            rx.mode = mode
            rx.low, rx.high = low, high
            rx._build_mode()
        self._rx(apply)
        self.cfg["mode"], self.cfg["bandwidth"] = mode, w
        self.vfos[self.active_vfo].update(mode=mode, bw=w)
        self._sync_views()

    def set_bandwidth(self, width: float):
        self.low, self.high = passband_for(self.mode, width)
        self._set_passband(self.low, self.high)

    def _set_passband(self, low: float, high: float):
        if high - low < 50:
            return
        self.low, self.high = low, high
        self._rx(lambda rx: rx.set_passband(low, high))
        self.cfg["bandwidth"] = high - low
        self.vfos[self.active_vfo]["bw"] = high - low
        self._sync_views()

    def set_step(self, step: int):
        self.step = int(step)
        self.cfg["step"] = self.step
        self._sync_views()

    def _goto_band(self, band):
        self.set_step(band.step)
        self.set_mode(band.mode)
        self.tune((band.start + band.end) / 2, snap=True)

    def _set_deemph(self, us):
        self.cfg["wfm_deemph_us"] = us

        def apply(rx):
            rx.wfm_deemph_tau = us * 1e-6
            rx._build_mode()
        self._rx(apply)

    def _set_squelch(self, db):
        self.cfg["squelch"] = db
        self._rx(lambda rx: setattr(rx.squelch, "threshold_db", float(db)))
        self.lcd.flags["SQL"] = db > -150
        self.lcd.update()

    def _auto_squelch(self):
        rx = self.engine.rx
        if rx is None:
            return
        self._sq_samples = []
        # mede o nível por ~0,5 s e ajusta 6 dB acima da mediana
        QTimer.singleShot(500, self._finish_auto_squelch)
        self._sq_collect = True

    def _finish_auto_squelch(self):
        self._sq_collect = False
        vals = sorted(getattr(self, "_sq_samples", []) or [self.engine.status["signal_db"]])
        floor = vals[len(vals) // 4]
        self.audio_panel.set_squelch(floor + 6)

    def _set_agc(self, on, speed):
        self.cfg["agc"], self.cfg["agc_speed"] = on, speed

        def apply(rx):
            rx.agc.enabled = on
            rx.agc.set_speed(speed)
        self._rx(apply)
        self.lcd.flags["AGC"] = on
        self.lcd.update()

    def _set_nb(self, on, thr):
        self.cfg["nb"] = on
        self._rx(lambda rx: (setattr(rx.nb, "enabled", on), setattr(rx.nb, "threshold", thr)))
        self.lcd.flags["NB"] = on
        self.lcd.update()

    def _set_nr(self, on, strength):
        self.cfg["nr"] = on
        self._rx(lambda rx: (setattr(rx.nr, "enabled", on), setattr(rx.nr, "strength", strength)))
        self.lcd.flags["NR"] = on
        self.lcd.update()

    def _set_notch(self, on, f):
        def apply(rx):
            rx.notch.enabled = on
            rx.notch.set_freq(f)
        self._rx(apply)
        self.lcd.flags["NOTCH"] = on
        self.lcd.update()

    def _set_eq(self, on, gains):
        self.cfg["eq_enabled"], self.cfg["eq_gains"] = on, gains

        def apply(rx):
            rx.eq.enabled = on
            rx.eq.set_gains(gains)
        self._rx(apply)
        self.lcd.flags["EQ"] = on
        self.lcd.update()

    def _set_decoders(self, d):
        self.engine.decoders_enabled = d
        self.cfg["decoders"] = d

    def _set_tone_squelch(self, tone):
        self.engine.tone_squelch = tone
        self.lcd.flags["TSQ"] = tone is not None
        self.lcd.update()

    def _audio_device(self, dev):
        self.cfg["audio_device"] = dev
        self.audio.stop()
        self.audio = AudioOutput(AUDIO_RATE, dev)
        self.audio.start()
        self.engine.audio = self.audio
        self.status_audio.setText("Áudio: OK" if self.audio.available else "Áudio indisponível")

    def _record_audio(self, on):
        if on:
            if not self.engine.running:
                self.audio_panel.rec_audio.setChecked(False)
                return
            p = self.engine.start_audio_recording(self.cfg["recordings_dir"])
            self.statusBar().showMessage(f"Gravando áudio em {p}", 5000)
        else:
            self.engine.stop_audio_recording()
        self._rec_flag()

    def _record_iq(self, on):
        if on:
            if not self.engine.running:
                self.audio_panel.rec_iq.setChecked(False)
                return
            p = self.engine.start_iq_recording(self.cfg["recordings_dir"])
            self.statusBar().showMessage(f"Gravando IQ em {p}", 5000)
        else:
            self.engine.stop_iq_recording()
        self._rec_flag()

    def _rec_flag(self):
        self.lcd.flags["REC"] = self.engine.recording_audio or self.engine.recording_iq
        self.lcd.update()

    # ================================================================== VFO / memórias
    def _vfo_action(self, act):
        cur = {"freq": self.engine.vfo, "mode": self.mode, "bw": self.high - self.low}
        self.vfos[self.active_vfo] = cur
        if act in ("A", "B"):
            self.active_vfo = act
        elif act == "swap":
            self.active_vfo = "B" if self.active_vfo == "A" else "A"
        elif act == "copy":
            other = "B" if self.active_vfo == "A" else "A"
            self.vfos[other] = dict(cur)
            return
        v = self.vfos[self.active_vfo]
        self.mode_panel.set_vfo(self.active_vfo)
        self.set_mode(v["mode"], v["bw"])
        self.tune(v["freq"])

    def recall_memory(self, ch: MemoryChannel):
        self._stop_scan()
        self._recall(ch)

    def _recall(self, ch: MemoryChannel):
        self.set_mode(ch.mode, ch.bandwidth)
        self.tune(ch.freq)
        self.current_mem = ch
        if ch.squelch is not None:
            self.audio_panel.set_squelch(ch.squelch)
        self._sync_views()

    def _save_current_memory(self):
        f = self.engine.vfo
        ch = MemoryChannel(name=f"{f / 1e6:.4f}", freq=f, mode=self.mode, bandwidth=self.high - self.low,
                           category="Favoritos", ctcss=self.engine.status.get("ctcss"))
        self.mem_panel.add_channel_dialog(ch)

    def _refresh_markers(self):
        c, fs = self.engine.center_freq, max(self.engine.sample_rate, 1)
        lo, hi = c - fs / 2, c + fs / 2
        self.wf.set_markers([(m.freq, m.name) for m in self.bank.in_range(lo, hi)])
        from ..memory import BAND_PLAN
        self.wf.set_bands([(max(b.start, lo), min(b.end, hi), b.name) for b in BAND_PLAN
                           if b.end > lo and b.start < hi])
        self._marker_center = c

    # ================================================================== varredura
    def _start_scan(self, kind, arg):
        self._sscan_stop()
        if not self.engine.running:
            QMessageBox.information(self, "Varredura", "Ligue o receptor antes de varrer.")
            return
        if self.audio_panel.squelch.value() <= -150:
            self._auto_squelch()
            QTimer.singleShot(700, lambda: self._start_scan(kind, arg))
            return
        if kind == "memory":
            chans = [c for c in (self.bank.by_category(arg) if arg else
                                 [c for c in self.bank.channels if c.favorite] or self.bank.channels)
                     if not c.skip_scan]
            if not chans:
                return
            items = chans
        else:
            f0, f1 = sorted(arg)
            n = int((f1 - f0) / self.step) + 1
            if n > 20000:
                QMessageBox.warning(self, "Varredura", "Faixa grande demais para o passo atual.")
                return
            items = [f0 + i * self.step for i in range(n)]
        self.scan = {"items": items, "i": -1, "t": 0.0, "held": False, "lost": 0.0,
                     "dwell": self.mem_panel.dwell.value() / 1000, "resume": self.mem_panel.resume.value()}
        self.lcd.flags["SCAN"] = True
        self._scan_next()

    def _scan_next(self):
        s = self.scan
        s["i"] = (s["i"] + 1) % len(s["items"])
        it = s["items"][s["i"]]
        if isinstance(it, MemoryChannel):
            self._recall(it)
        else:
            self.tune(it)
        s["t"] = time.monotonic()
        s["held"] = False

    def _scan_tick(self):
        s = self.scan
        if s is None:
            return
        now = time.monotonic()
        open_ = self.engine.status["sq_open"]
        if now - s["t"] < s["dwell"]:
            return
        if open_:
            s["held"] = True
            s["lost"] = 0.0
            return
        if s["held"]:
            if s["resume"] <= 0:
                return
            if not s["lost"]:
                s["lost"] = now
                return
            if now - s["lost"] < s["resume"]:
                return
        self._scan_next()

    def _stop_scan(self):
        if self.scan is not None:
            self.scan = None
            self.lcd.flags["SCAN"] = False
            self.lcd.update()

    # ================================================================== favoritos / prontas
    def _memories_changed(self):
        self._refresh_markers()
        self.fav_bar.refresh(self.bank.channels, self.engine.vfo)

    def _open_presets(self):
        dlg = PresetDialog(self)
        if dlg.exec():
            n = import_packs(self.bank, dlg.selected_keys(), favorite=dlg.fav.isChecked())
            self.bank.save()
            self.mem_panel.refresh()
            self._memories_changed()
            self.statusBar().showMessage(f"{n} canais adicionados às memórias", 6000)

    def _fav_add_current(self):
        f = self.engine.vfo
        ch = MemoryChannel(name=f"{f / 1e6:.4f}", freq=f, mode=self.mode, bandwidth=self.high - self.low,
                           category="Favoritos", favorite=True)
        self.mem_panel.add_channel_dialog(ch)

    def _unfavorite(self, ch):
        ch.favorite = False
        self.bank.save()
        self.mem_panel.refresh()
        self._memories_changed()

    def _mem_name(self, f: float, tol: float = 3000) -> str:
        best = min(self.bank.channels, key=lambda c: abs(c.freq - f), default=None)
        return best.name if best is not None and abs(best.freq - f) <= tol else ""

    # ================================================================== scanner por espectro
    def _sscan_start(self, opts: dict):
        if not self.engine.running:
            QMessageBox.information(self, "Scanner", "Ligue o receptor antes de varrer.")
            self.scan_panel.set_running(False)
            return
        if not self.engine.source.tunable and (opts["start"] < self.engine.center_freq - self.engine.sample_rate / 2
                                               or opts["end"] > self.engine.center_freq + self.engine.sample_rate / 2):
            QMessageBox.information(self, "Scanner", "Com arquivo IQ só é possível varrer dentro da faixa gravada.")
            self.scan_panel.set_running(False)
            return
        self._stop_scan()
        old = self.sscan
        cfg = ScannerConfig(**opts)
        if old is not None:
            cfg.lockouts = old.cfg.lockouts
        self.set_mode(opts["mode"], opts["bandwidth"])
        sc = SpectrumScanner(self.engine, cfg)
        if old is not None and abs(old.cfg.start - cfg.start) < 1 and abs(old.cfg.end - cfg.end) < 1:
            sc.hits = old.hits  # continua acumulando a mesma faixa
        self.sscan = sc
        sc.start(time.monotonic())
        self.scan_panel.set_running(True)
        self.lcd.flags["SCAN"] = True

    def _sscan_stop(self):
        sc = self.sscan
        if sc is not None and sc.running:
            sc.stop()
            self.engine.tune(self.engine.vfo)
            self.lcd.flags["SCAN"] = False
            self.lcd.update()
        self.scan_panel.set_running(False)

    def _sscan_listen(self, f, mode, bw):
        self._sscan_stop()
        self.set_mode(mode, bw)
        self.tune(f)

    def _sscan_save(self, freqs, category):
        opts = self.scan_panel.options()
        n = 0
        for f in freqs:
            if self._mem_name(f, 500):
                continue
            self.bank.add(MemoryChannel(name=f"{f / 1e6:.4f}", freq=f, mode=opts["mode"],
                                        bandwidth=opts["bandwidth"], category=category or "Descobertas",
                                        notes=time.strftime("Scanner %d/%m/%Y %H:%M")))
            n += 1
        self.bank.save()
        self.mem_panel.refresh()
        self._memories_changed()
        self.statusBar().showMessage(f"{n} frequências salvas em '{category}'", 5000)

    def _sscan_lock(self, freqs):
        if self.sscan is None:
            return
        for f in freqs:
            self.sscan.lockout(f)
        self._update_hits(force=True)

    def _sscan_unlock(self):
        if self.sscan is not None:
            self.sscan.cfg.lockouts.clear()

    def _sscan_clear(self):
        if self.sscan is not None:
            self.sscan.hits.clear()
        self._update_hits(force=True)

    def _update_hits(self, force=False):
        now = time.monotonic()
        if self.sscan is None or (not force and now - self._hits_t < 0.7):
            return
        self._hits_t = now
        self.scan_panel.show_hits(self.sscan.sorted_hits(), self._mem_name, now)
        sc = self.sscan
        if sc.running:
            where = (f"escutando {sc.listen_freq / 1e6:.4f} MHz" if sc.state == "listen" else
                     f"segmento {sc._seg + 1}/{len(sc._segments)}")
            self.scan_panel.status.setText(
                f"Varrendo {sc.cfg.start / 1e6:.3f}–{sc.cfg.end / 1e6:.3f} MHz — {where}<br>"
                f"{sc.sweeps} varreduras · ~{sc.channels_per_second():.0f} canais/s · piso {sc.floor_db:.0f} dBFS · "
                f"{len(sc.hits)} ativas · {len(sc.cfg.lockouts)} bloqueadas")
        else:
            self.scan_panel.status.setText(f"Parado — {len(sc.hits)} frequências na lista")

    def _auto_record(self, on, min_s):
        if on:
            if self.audio_panel.squelch.value() <= -150 and self.engine.tone_squelch is None:
                self._auto_squelch()
                self.statusBar().showMessage("Squelch ajustado automaticamente para a gravação por atividade", 5000)
            folder = str(Path(self.cfg["recordings_dir"]) / "atividade")
            self.engine.activity_rec = ActivityRecorder(folder, AUDIO_RATE, min_s=min_s)
            self.lcd.flags["REC"] = True
        else:
            rec, self.engine.activity_rec = self.engine.activity_rec, None
            if rec is not None:
                ev = rec.close()
                if ev:
                    self.scan_panel.add_activity(ev, self._mem_name(ev["freq"]))
            self._rec_flag()
        self.lcd.update()

    # ================================================================== waterfall
    def _levels(self):
        lo, hi = self.wf_min.value(), self.wf_max.value()
        self.wf.set_levels(lo, hi)
        self.cfg["wf_min_db"], self.cfg["wf_max_db"] = lo, hi

    def _auto_levels(self):
        r = self.wf.auto_levels()
        if r:
            for s, v in ((self.wf_min, r[0]), (self.wf_max, r[1])):
                s.blockSignals(True)
                s.setValue(int(v))
                s.blockSignals(False)
            self.cfg["wf_min_db"], self.cfg["wf_max_db"] = r

    # ================================================================== atualização
    def _sync_views(self):
        vfo = self.engine.vfo
        self.wf.step = self.step
        self.wf.set_vfo(vfo, self.low, self.high)
        self.mode_panel.show_mode(self.mode, self.high - self.low, self.step)
        self._update_lcd()

    def _update_lcd(self):
        self.fav_bar.mark_current(self.engine.vfo)
        lcd = self.lcd
        lcd.set_freq(self.engine.vfo)
        lcd.mode = self.mode
        lcd.bandwidth = self.high - self.low
        lcd.step = self.step
        lcd.vfo_name = f"VFO {self.active_vfo}" if self.current_mem is None else "MEM"
        if self.current_mem:
            idx = self.bank.channels.index(self.current_mem) + 1 if self.current_mem in self.bank.channels else 0
            lcd.mem_label = f"M{idx:03d} {self.current_mem.name[:14]}"
        else:
            lcd.mem_label = ""
        b = band_for(self.engine.vfo)
        lcd.band_label = b.name if b else ""
        lcd.flags["AGC"] = self.audio_panel.agc.isChecked() and self.mode not in ("NFM", "WFM")
        lcd.update()

    def _tick(self):
        eng = self.engine
        lines = []
        while eng.wf_lines:
            try:
                lines.append(eng.wf_lines.popleft())
            except IndexError:
                break
        sc = self.sscan
        if sc is not None and sc.running:
            now = time.monotonic()
            for spec, center, fs in lines:
                for ev in sc.feed(spec, center, fs, now):
                    if ev[0] == "listen":
                        self.statusBar().showMessage(f"Scanner: sinal em {ev[1] / 1e6:.4f} MHz "
                                                     f"{self._mem_name(ev[1])}", 4000)
                        self._sync_views()
                    elif ev[0] == "resume":
                        self._sync_views()
            self._update_hits()
        for spec, center, fs in lines[-8:]:
            self.wf.add_line(spec, center, fs)
        if lines and abs(getattr(self, "_marker_center", 0) - eng.center_freq) > 1:
            self._refresh_markers()
            self.wf.set_vfo(eng.vfo, self.low, self.high)

        st = eng.status
        if eng.running:
            dbm, s = dbfs_to_s_units(st["signal_db"], self.cfg["s_meter_cal"])
            self.lcd.set_signal(dbm, s, st["sq_open"] and self.audio_panel.squelch.value() > -150)
            if getattr(self, "_sq_collect", False):
                self._sq_samples.append(st["signal_db"])
            tone = st.get("ctcss")
            self.lcd.ctcss_text = f"CTCSS {tone:.1f}" if tone else ""
            self.dec_panel.set_ctcss(tone)
            self.status_cpu.setText(f"DSP {st['cpu'] * 100:4.0f}%  perdas {st['dropped']}  "
                                    f"centro {eng.center_freq / 1e6:.4f} MHz")
        elif self.rx_panel.start_btn.isChecked():
            self.stop_source()

        n = 0
        while not eng.events.empty() and n < 50:
            kind, data, ts = eng.events.get_nowait()
            n += 1
            if kind == "aprs":
                self.dec_panel.add_aprs(data, ts)
                self.statusBar().showMessage(f"APRS: {data.raw}", 4000)
            elif kind == "dtmf":
                self.dec_panel.add_dtmf(data, ts)
            elif kind == "activity":
                self.scan_panel.add_activity(data, self._mem_name(data["freq"]))
            elif kind == "error":
                self.statusBar().showMessage(data, 8000)
        self._scan_tick()

    # ================================================================== layout / saída
    def _restore_layout(self):
        s = QSettings("PT2VHF", "SDRTool")
        geo, state = s.value("geometry"), s.value("state")
        self._default_state = self.saveState()
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        if isinstance(state, QByteArray):
            self.restoreState(state)

    def _reset_layout(self):
        self.restoreState(self._default_state)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Atalhos", (
            "<b>Display LCD</b>: roda do mouse sobre um dígito altera o dígito; clique em cima/baixo do dígito;"
            " digite a frequência em MHz + Enter; setas ←/→ passo, ↑/↓ passo×10.<br>"
            "<b>Waterfall</b>: clique sintoniza; arraste o passband para sintonizar ou as bordas para largura;"
            " roda = zoom; Ctrl+roda = sintonia; duplo clique = zoom total.<br>"
            "<b>Teclado</b>: Alt+N/W/A/U/L/C modos; Ctrl+←/→ passo; Ctrl+↑/↓ passo×10; Ctrl+M salvar memória;"
            " Ctrl+B trocar VFO; Ctrl+S squelch automático; Ctrl+L níveis automáticos; Ctrl+Shift+M mudo;"
            " Esc parar varredura."))

    def closeEvent(self, ev):
        s = QSettings("PT2VHF", "SDRTool")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("state", self.saveState())
        self.cfg["vfo_freq"] = self.vfos["A"]["freq"] if self.active_vfo != "A" else self.engine.vfo
        self.cfg["fft_size"] = self.engine.fft_size
        self.cfg["my_locator"] = self.dec_panel.locator.text()
        self.cfg.save()
        self.bank.save()
        self.engine.stop()
        self.audio.stop()
        super().closeEvent(ev)
