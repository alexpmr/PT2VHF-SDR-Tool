"""Janela principal do PT2VHF SDR Tool."""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..audio import AudioOutput
from ..config import Config, config_dir
from ..dsp.demod import dbfs_to_s_units
from ..dsp.receiver import AUDIO_RATE, MODES, passband_for
from ..engine import Engine
from ..memory import MemoryBank, MemoryChannel, band_for
from ..occupancy import OccupancyHistory
from ..sources.base import SourceError
from ..audio import ActivityRecorder
from ..presets import import_packs
from ..scanner import ScannerConfig, SpectrumScanner
from .lcd import THEMES, LCDDisplay
from .assist_panels import AssistBox, ExtrasPanel, TimeShiftBox, UpdateController
from .listening import FavoritesBar, PresetDialog, ScannerPanel
from .settings_panel import SettingsPanel
from .bandkeys import BandKeys
from .display_settings import DisplaySettings
from .occupancy_panel import OccupancyPanel
from .traffic_panel import SourceTab
from .satellite_panel import SatellitePanel
from .sonde_decoder_panel import SondeDecoderPanel
from ..i18n import LANGUAGES, apply_language, flag_icon, translate
from .rigctl_panel import RigCtlPanel
from .live_captions_panel import LiveCaptionsPanel
from .analog import AnalogPanel
from .panels import AudioPanel, DecoderPanel, MemoryPanel, ModePanel, ReceiverPanel
from .waterfall import COLORMAPS, SpectrumWaterfall

log = logging.getLogger(__name__)

LEVELS = ["Essencial", "Intermediário", "Avançado"]

STYLE = """
QMainWindow, QWidget { background: #161a20; color: #d8dee6; font-size: 12px; }
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
QPushButton#versionButton { background: #155a3e; border: 1px solid #30a579; color: #e6fff4; padding: 4px 10px; }
QPushButton#versionButton:hover { background: #1b6f4c; }
QFrame#header { background: #10141a; border: 1px solid #232a33; border-radius: 6px; }
QLabel#headline { font-size: 18px; font-weight: 800; color: #f0b44a; letter-spacing: 1px; padding-right: 8px; }
QLabel#headerSummary { color: #9aa6b2; font-size: 11px; padding-left: 6px; }
QLabel#utcLabel { font-size: 12px; font-weight: 700; color: #f6dca8; padding: 4px 6px; background: #232a33;
  border: 1px solid #39444f; border-radius: 5px; }
QTabWidget#mainTabs::pane { border: 0; }
QTabWidget#mainTabs > QTabBar::tab { padding: 9px 18px; font-size: 13px; background: #1d232b; color: #bfc8d2; }
QTabWidget#mainTabs > QTabBar::tab:selected { background: #2a323d; color: #f0b44a; border-bottom: 2px solid #f0b44a; }
QToolBar#wfToolbar { background: transparent; border: 0; spacing: 6px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1500, 950)
        self.cfg = Config()
        self.bank = MemoryBank(config_dir() / "memorias.json")
        self.occupancy = OccupancyHistory(config_dir() / "ocupacao_24h.json")
        self.audio = AudioOutput(AUDIO_RATE, self.cfg["audio_device"])
        self.audio.start()
        self.engine = Engine(self.audio)
        self.engine.vfo = self.cfg["vfo_freq"]
        self.engine.fft_size = self.cfg["fft_size"]
        self.engine.wf_speed = self.cfg["wf_speed"]
        self.engine.decoders_enabled = dict(self.cfg["decoders"])
        self.engine.timeshift_seconds = float(self.cfg.get("timeshift_s", 20))
        from ..sources.rtlsdr_source import set_preference
        set_preference(self.cfg.get("rtl_library", "auto"))

        self.mode = self.cfg["mode"]
        self.low, self.high = passband_for(self.mode, self.cfg["bandwidth"])
        self.step = self.cfg["step"]
        self.vfos = {"A": {"freq": self.cfg["vfo_freq"], "mode": self.mode, "bw": self.cfg["bandwidth"]},
                     "B": {"freq": self.cfg["vfo_b_freq"], "mode": "NFM", "bw": 12000}}
        self.active_vfo = "A"
        self.current_mem: MemoryChannel | None = None
        self.auto_mode = bool(self.cfg.get("auto_mode", False))
        self.auto_tune = bool(self.cfg.get("auto_tune", True))
        self._sel_gen = 0
        self._neighbor_hops = 0
        self.scan = None

        self._build_ui()
        self._wire()
        self._restore_layout()
        self.apply_level(self.cfg.get("ui_level", "Avançado"))
        self._language_selected()
        self._apply_receiver_settings()
        self._refresh_markers()
        if self.cfg.get("source") == "RTL-SDR" and not self.cfg.get("rx_ever_connected") and not self.cfg.get("device_name"):
            QTimer.singleShot(350, self._show_initial_receiver_setup)
        self.settings_panel.pres_btn.clicked.connect(lambda: self.set_presentation(not self._presenting))
        if not os.environ.get("PT2VHF_NO_AUTOCONNECT"):
            QTimer.singleShot(900, self._auto_reconnect)
        if self.cfg.get("presentation") and not os.environ.get("PT2VHF_NO_STARTUP_DIALOGS"):
            QTimer.singleShot(300, lambda: self.set_presentation(True))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self._clock_tick)
        self.clock.start(1000)

    # ================================================================== UI
    def _build_ui(self):
        """Padrão PT2VHF (como no Sat Tool): cabeçalho com versão/atualização e abas superiores."""
        from PySide6.QtWidgets import QSplitter, QTabWidget
        self.setStyleSheet(STYLE)
        self.rx_panel = ReceiverPanel(self.cfg)
        self.mode_panel = ModePanel(self.cfg)
        self.audio_panel = AudioPanel(self.cfg)
        self.mem_panel = MemoryPanel(self.bank)
        self.dec_panel = DecoderPanel(self.cfg)
        # Preserva APRS / DTMF / CTCSS, mas remove o contêiner principal genérico.
        self.adsb_panel = SourceTab("ADS-B", self.cfg)
        self.ais_panel = SourceTab("AIS", self.cfg)
        self.sonde_panel = SondeDecoderPanel(self.cfg, lambda: self.engine.vfo)
        self.sonde_feed = SourceTab("Sonda", self.cfg)
        self.sonde_area = QTabWidget()
        self.sonde_area.addTab(self.sonde_panel, "Recepção RF · RS41")
        self.sonde_area.addTab(self.sonde_feed, "Telemetria externa")
        self.sonde_worker = None
        self.scan_panel = ScannerPanel(self.cfg, self.bank.categories + ["Descobertas"])
        self.occupancy_panel = OccupancyPanel(self.occupancy)
        self.scan_panel.tabs.addTab(self.occupancy_panel, "Ocupação 24 h")
        self.live_captions_panel = LiveCaptionsPanel(self.cfg)
        self.scan_panel.tabs.addTab(self.live_captions_panel, "Legendas ao vivo")
        self.scan_panel.tabs.addTab(self.dec_panel, "APRS / DTMF / CTCSS")
        self.sscan: SpectrumScanner | None = None
        self._hits_t = 0.0
        self.assist = AssistBox()
        self.mode_panel.layout().insertWidget(self.mode_panel.layout().count() - 1, self.assist)
        self.tshift = TimeShiftBox(self.cfg.get("timeshift_s", 20))
        self.audio_panel.layout().insertWidget(self.audio_panel.layout().count() - 1, self.tshift)
        self.extras_panel = ExtrasPanel()
        self.settings_panel = SettingsPanel(self.cfg, LEVELS, list(THEMES))
        self.web = None
        from collections import deque
        self._web_aprs = deque(maxlen=30)
        self._web_state = {}
        self.transcriber = None
        self.caption_worker = None
        self._assist_busy = False
        self._presenting = False
        self._quiet_start = False
        self._quiet_error = ""
        self._weak_restore = None
        self._last_occupancy_refresh = 0.0

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(4, 4, 4, 0)
        outer.setSpacing(3)
        self.header = self._build_header()
        outer.addWidget(self.header)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # aba Receptor: display + favoritos + waterfall, painel de áudio à direita
        left = QWidget()
        cl = QVBoxLayout(left)
        cl.setContentsMargins(0, 0, 0, 0)
        self.lcd = LCDDisplay()
        self.lcd.set_theme(self.cfg["lcd_theme"])
        cl.addWidget(self.lcd)
        self.analog_panel = AnalogPanel(self.cfg.get("analog_style", "Valvulado"))
        self.analog_panel.setVisible(bool(self.cfg.get("analog_enabled", False)))
        cl.addWidget(self.analog_panel)
        self.caption_label = QLabel("")
        self.caption_label.setWordWrap(True)
        self.caption_label.setObjectName("bigLabel")
        self.caption_label.setMinimumHeight(36)
        self.caption_label.setVisible(False)
        cl.addWidget(self.caption_label)
        self.band_bar = BandKeys(self.cfg.get("bands_visible"), self.lcd)
        self.lcd.attach_band_keys(self.band_bar)
        self.fav_bar = FavoritesBar()
        self.fav_bar.refresh(self.bank.channels, self.engine.vfo)
        cl.addWidget(self.fav_bar)
        self.wf_toolbar = self._build_wf_toolbar()
        cl.addWidget(self.wf_toolbar)
        self.wf = SpectrumWaterfall()
        self.wf.set_colormap(self.cfg["wf_colormap"])
        self.wf.set_levels(self.cfg["wf_min_db"], self.cfg["wf_max_db"])
        self.wf.avg_alpha = self.cfg["spectrum_avg"]
        self.wf.setMinimumHeight(175)
        cl.addWidget(self.wf, 1)
        self.audio_scroll = _scroll(self.audio_panel)
        self.audio_scroll.setMinimumWidth(max(330, self.audio_panel.minimumSizeHint().width() + 18))
        self.main_split = QSplitter(Qt.Horizontal)
        self.main_split.addWidget(left)
        self.main_split.addWidget(self.audio_scroll)
        self.main_split.setStretchFactor(0, 1)
        self.main_split.setStretchFactor(1, 0)
        self.main_split.setCollapsible(0, False)
        self.main_split.setSizes([1100, self.audio_scroll.minimumWidth()])
        self._default_split = self.main_split.saveState()

        self.settings_tabs = QTabWidget()
        self.settings_tabs.setObjectName("settingsTabs")
        self.settings_tabs.addTab(_scroll(self.rx_panel), "Receptor")
        self.settings_tabs.addTab(_scroll(self.mode_panel), "Modo / Filtro")
        self.display_panel = DisplaySettings(self.cfg, self.lcd_theme)
        self.settings_tabs.addTab(_scroll(self.display_panel), "Display")
        self.settings_tabs.addTab(_scroll(self.settings_panel), "Geral · Web · Atualizações")
        self.sat_panel = SatellitePanel(self.cfg)
        self.rigctl_panel = RigCtlPanel(self.cfg, lambda: (self.engine.vfo, self.mode))
        self.settings_tabs.addTab(_scroll(self.rigctl_panel), "CAT · Hamlib")
        self.pages = {}
        for key, title, w in (("rx", "Receptor", self.main_split),
                              ("mem", "Memórias / Varredura", _scroll(self.mem_panel)),
                              ("scan", "Scanner", _scroll(self.scan_panel)),
                              ("adsb", "ADS-B", _scroll(self.adsb_panel)),
                              ("ais", "AIS", _scroll(self.ais_panel)),
                              ("sondes", "Sondas Meteorológicas", self.sonde_area),
                              ("extras", "Receptores extras", _scroll(self.extras_panel)),
                              ("sat", "Satélites", _scroll(self.sat_panel)),
                              ("settings", "Configurações", self.settings_tabs)):
            self.tabs.addTab(w, title)
            self.pages[key] = w

        self.status_src = QLabel("Parado")
        self.status_cpu = QLabel("")
        self.status_audio = QLabel("Áudio: OK" if self.audio.available else "Áudio indisponível")
        if not self.audio.available:
            self.status_audio.setToolTip(self.audio.error)
        for w in (self.status_src, self.status_cpu, self.status_audio):
            self.statusBar().addPermanentWidget(w)
        self._build_menu()

    def _build_header(self):
        from PySide6.QtWidgets import QFrame, QHBoxLayout
        box = QFrame()
        box.setObjectName("header")
        h = QHBoxLayout(box)
        h.setContentsMargins(8, 4, 8, 4)
        title = QLabel(f"PT2VHF  SDR TOOL   v{__version__}")
        title.setObjectName("headline")
        h.addWidget(title)
        self.version_btn = QPushButton("Verificar atualizações")
        self.version_btn.setObjectName("versionButton")
        self.updates = UpdateController(self, self.version_btn)
        h.addWidget(self.version_btn)
        self.hdr_summary = QLabel("Receptor parado")
        self.hdr_summary.setObjectName("headerSummary")
        h.addWidget(self.hdr_summary, 1)
        self.power_btn = QPushButton("▶  Ligar")
        self.power_btn.setObjectName("powerButton")
        self.power_btn.setCheckable(True)
        self.power_btn.setMinimumWidth(120)
        self.power_btn.setToolTip("Liga/desliga o receptor (fonte e dispositivo em Configurações → Receptor)")
        self.power_btn.clicked.connect(lambda on: self.rx_panel.start_btn.setChecked(on))
        h.addWidget(self.power_btn)
        self.pres_btn = QPushButton("Tela cheia")
        self.pres_btn.setToolTip("Modo apresentação: tela cheia sem barras do Windows (F11; Esc sai)")
        self.pres_btn.clicked.connect(lambda: self.set_presentation(not self._presenting))
        h.addWidget(self.pres_btn)
        self.language_combo = QComboBox()
        self.language_combo.setToolTip("Idioma da interface (tradução parcial por catálogo)")
        self.language_combo.setMaximumWidth(180)
        for code, label, country in LANGUAGES:
            self.language_combo.addItem(flag_icon(country), label, code)
        index = self.language_combo.findData(self.cfg.get("language", "pt"))
        self.language_combo.setCurrentIndex(max(0, index))
        h.addWidget(self.language_combo)
        self.utc_label = QLabel("")
        self.utc_label.setObjectName("utcLabel")
        h.addWidget(self.utc_label)
        return box

    def _set_running_ui(self, running: bool):
        self.rx_panel.set_running(running)
        self.power_btn.setChecked(running)
        self.power_btn.setText(translate("■  Desligar" if running else "▶  Ligar", self.cfg.get("language", "pt")))
        if not running:
            self.hdr_summary.setText("Receptor parado")

    def _clock_tick(self):
        self.lcd.update()
        self.utc_label.setText(time.strftime("%H:%M:%S UTC", time.gmtime()))

    def _build_wf_toolbar(self):
        from PySide6.QtWidgets import QSizePolicy, QToolBar
        row = QToolBar()
        row.setObjectName("wfToolbar")
        row.setMovable(False)  # QToolBar recolhe o que não cabe no botão »
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
        row.addSeparator()
        row.addWidget(QLabel("Zoom:"))
        for label, span in (("Total", None), ("500k", 500e3), ("200k", 200e3), ("50k", 50e3), ("10k", 10e3)):
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.clicked.connect(lambda _=False, s=span: self.wf.reset_zoom() if s is None else self.wf.zoom_to_vfo(s))
            row.addWidget(b)
        self.center_btn = QPushButton("Centralizar")
        self.center_btn.setToolTip("Centraliza o waterfall no VFO sem alterar o zoom (Ctrl+E)")
        self.center_btn.clicked.connect(self._center_waterfall)
        row.addWidget(self.center_btn)
        self.keep_center = QCheckBox("Seguir VFO")
        self.keep_center.setChecked(bool(self.cfg.get("wf_keep_vfo_centered", False)))
        self.keep_center.toggled.connect(self._toggle_keep_center)
        row.addWidget(self.keep_center)
        self.weak_btn = QPushButton("Sinal fraco · DSP")
        self.weak_btn.setCheckable(True)
        self.weak_btn.setToolTip("Ativa NR, NB e AGC para melhorar a escuta; utiliza DSP clássico, não IA neural.")
        self.weak_btn.toggled.connect(self._weak_signal_toggled)
        row.addWidget(self.weak_btn)
        self.live_btn = QPushButton("Legendas")
        self.live_btn.setCheckable(True)
        self.live_btn.setToolTip("Transcrição local em blocos da fonia que está sendo ouvida; faster-whisper opcional")
        row.addWidget(self.live_btn)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(spacer)
        self.lcd_theme = QComboBox()
        self.lcd_theme.addItems(list(THEMES))
        self.lcd_theme.setCurrentText(self.cfg["lcd_theme"])
        self.level_combo = QComboBox()
        self.level_combo.addItems(LEVELS)
        self.level_combo.setToolTip("Quantidade de recursos na tela: Essencial, Intermediário ou Avançado")
        row.addWidget(QLabel("Interface:"))
        row.addWidget(self.level_combo)
        # nível mínimo (0 essencial, 1 intermediário, 2 avançado) de cada item da barra
        lv = {self.fft: 2, self.avg: 2, self.peak: 2, self.wf_min: 1, self.wf_max: 1, self.speed: 1, self.cmap: 1}
        self._tb_levels = []
        for a in row.actions():
            w = row.widgetForAction(a)
            level = lv.get(w, 0)
            if isinstance(w, QLabel):
                level = {"Piso": 1, "Teto": 1, "Média": 2}.get(w.text(), 0)
            self._tb_levels.append((a, level))
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
        self._tab_actions = []
        for i in range(self.tabs.count()):
            a = QAction(f"Aba {self.tabs.tabText(i)}", self, shortcut=QKeySequence(f"Ctrl+{i + 1}"))
            a.triggered.connect(lambda _=False, w=self.tabs.widget(i): self.tabs.setCurrentWidget(w))
            v.addAction(a)
            self.addAction(a)
            self._tab_actions.append(a)
        self.audio_action = QAction("Painel de áudio / DSP", self, checkable=True, checked=True)
        self.audio_action.toggled.connect(self.audio_scroll.setVisible)
        v.addAction(self.audio_action)
        v.addSeparator()
        self.pres_action = QAction("Modo apresentação (tela cheia)", self, checkable=True,
                                   shortcut=QKeySequence("F11"))
        self.pres_action.triggered.connect(self.set_presentation)
        v.addAction(self.pres_action)
        self.addAction(self.pres_action)  # funciona com o menu oculto
        v.addSeparator()
        from PySide6.QtGui import QActionGroup
        grp = QActionGroup(self)
        self._level_actions = []
        for name in LEVELS:
            a = QAction(name, self, checkable=True)
            a.triggered.connect(lambda _=False, n=name: self.apply_level(n))
            grp.addAction(a)
            v.addAction(a)
            self._level_actions.append(a)
        v.addSeparator()
        a = QAction("Restaurar layout padrão", self)
        a.triggered.connect(self._reset_layout)
        v.addAction(a)
        h = mb.addMenu("A&juda")
        a = QAction("Preparar RTL-SDR (driver WinUSB)…", self)
        a.triggered.connect(self._prepare_rtlsdr)
        h.addAction(a)
        a = QAction("Diagnóstico do RTL-SDR…", self)
        a.triggered.connect(self._diagnose_rtlsdr)
        h.addAction(a)
        h.addSeparator()
        a = QAction("Verificar atualizações…", self)
        a.triggered.connect(lambda: self.updates.check(manual=True))
        h.addAction(a)
        a = QAction("Atalhos de teclado", self)
        a.triggered.connect(self._show_shortcuts)
        h.addAction(a)
        a = QAction("Sobre", self)
        a.triggered.connect(lambda: QMessageBox.about(
            self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Receptor SDR para radioamadores.<br>"
                            "RTL-SDR, rtl_tcp, SoapySDR, arquivos IQ.<br>Decodificação APRS, DTMF e CTCSS.<br><br>"
                            "Downloads e atualizações oficiais somente em "
                            "<a href='https://www.pt2vhf.com/sdr'>www.pt2vhf.com</a>."))
        h.addAction(a)

    def _language_selected(self, *_):
        code = self.language_combo.currentData()
        if code is None:
            return
        self.cfg["language"] = code
        self.cfg.save()
        apply_language(self, code)
        self.statusBar().showMessage(
            "Idioma alterado. Partes ainda não traduzidas mantêm o português.", 7000)

    # ================================================================== ligações
    def _wire(self):
        lcd, wf, rp, mp, ap, mem, dp = (self.lcd, self.wf, self.rx_panel, self.mode_panel,
                                        self.audio_panel, self.mem_panel, self.dec_panel)
        self.language_combo.currentIndexChanged.connect(self._language_selected)
        self.live_btn.toggled.connect(self._toggle_live_captions)
        self.band_bar.selected.connect(self._band_button)
        self.display_panel.bandsChanged.connect(self._set_visible_bands)
        self.display_panel.analogChanged.connect(self._analog_display_changed)
        lcd.freqChanged.connect(self.tune)
        lcd.stepRequested.connect(lambda n: self.tune(self.engine.vfo + n * self.step, snap=True))
        wf.tuneRequested.connect(self.select_transmission)
        lcd.modeClicked.connect(self.choose_mode)
        lcd.neighborRequested.connect(self.jump_neighbor)
        lcd.autoTuneToggled.connect(lambda: self._set_auto_tune(not self.auto_tune))
        wf.passbandChanged.connect(self._set_passband)
        wf.panRequested.connect(self._pan_to)

        rp.startRequested.connect(self.start_source)
        rp.stopRequested.connect(self.stop_source)
        rp.gainChanged.connect(lambda g: self._src_call("set_gain", g, cfg="gain"))
        rp.ppmChanged.connect(lambda v: self._src_call("set_ppm", v, cfg="ppm"))
        rp.biasTeeChanged.connect(lambda v: self._src_call("set_bias_tee", v, cfg="bias_tee"))
        rp.directSamplingChanged.connect(lambda v: (self._src_call("set_direct_sampling", v, cfg="direct_sampling"),
                                                    self._refresh_band_keys()))

        mp.modeChanged.connect(self.choose_mode)
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
        ap.vox.setChecked(bool(self.cfg.get("vox", False)))
        ap.vox.toggled.connect(lambda v: (self.cfg.__setitem__("vox", v), self._rec_flag()))
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
        self.rigctl_panel.readReceived.connect(self._cat_received)
        self.sat_panel.tuneReceiveRequested.connect(self.tune)
        self.sonde_panel.startRequested.connect(self._start_sonde)
        self.sonde_panel.stopRequested.connect(self._stop_sonde)
        self.sonde_panel.captureRequested.connect(self._capture_sonde_iq)

        self.fft.currentIndexChanged.connect(lambda _: self._set_engine("fft_size", self.fft.currentData()))
        self.cmap.currentTextChanged.connect(lambda n: (self.wf.set_colormap(n), self.cfg.__setitem__("wf_colormap", n)))
        self.wf_min.valueChanged.connect(self._levels)
        self.wf_max.valueChanged.connect(self._levels)
        self.wf_auto.clicked.connect(self._auto_levels)
        self.speed.currentIndexChanged.connect(lambda _: self._set_engine("wf_speed", self.speed.currentData()))
        self.avg.valueChanged.connect(lambda v: (setattr(self.wf, "avg_alpha", v / 100), self.cfg.__setitem__("spectrum_avg", v / 100)))
        self.peak.toggled.connect(lambda v: (setattr(self.wf, "peak_hold", v), self.wf.clear_peak()))
        self.level_combo.currentTextChanged.connect(self.apply_level)
        self.lcd_theme.currentTextChanged.connect(lambda n: (self.lcd.set_theme(n), self.cfg.__setitem__("lcd_theme", n)))

        ab = self.assist
        ab.autotuneRequested.connect(lambda: self._assist_autotune(manual=True))
        ab.detectRequested.connect(self._assist_detect)
        ab.filterRequested.connect(self._assist_filter)
        self._cont_timer = QTimer(self)
        self._cont_timer.timeout.connect(lambda: self._assist_autotune(manual=False))
        ab.cont.toggled.connect(lambda on: self._cont_timer.start(10_000) if on else self._cont_timer.stop())

        ts = self.tshift
        ts.bufferChanged.connect(self._set_timeshift)
        ts.replayRequested.connect(self._replay)
        ts.liveRequested.connect(lambda: self.engine.stop_replay())

        xp = self.extras_panel
        xp.addRequested.connect(self._extra_add)
        xp.removeRequested.connect(self._extra_remove)
        xp.changed.connect(lambda _ex: self._extra_markers())
        xp.tuneMainRequested.connect(lambda f, m: (self.set_mode(m), self.tune(f)))

        self.scan_panel.transcribe.toggled.connect(self._toggle_transcription)
        sp2 = self.settings_panel
        sp2.changed.connect(self._setting_changed)
        sp2.checkUpdatesNow.connect(lambda: self.updates.check(manual=True))
        sp2.webApply.connect(self._web_apply)
        sp2.webOpen.connect(self._web_open)
        sp2.webCopy.connect(self._web_copy)
        if self.cfg.get("web_enabled", False):
            QTimer.singleShot(700, self._web_apply)
        # padrão PT2VHF: anúncio ao abrir, resultado da última atualização e verificação automática
        if not os.environ.get("PT2VHF_NO_STARTUP_DIALOGS"):
            QTimer.singleShot(1800, self._startup_notices)
        QTimer.singleShot(12_000, lambda: self.updates.check(manual=False))
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(lambda: self.updates.check(manual=False))
        self._update_timer.start(6 * 3600 * 1000)

        # atalhos (estilo KiwiSDR / SDR#)
        for keys, fn in (
            ("Alt+N", lambda: self.choose_mode("NFM")), ("Alt+W", lambda: self.choose_mode("WFM")),
            ("Alt+A", lambda: self.choose_mode("AM")), ("Alt+U", lambda: self.choose_mode("USB")),
            ("Alt+L", lambda: self.choose_mode("LSB")), ("Alt+C", lambda: self.choose_mode("CW")),
            ("Ctrl+Right", lambda: self.tune(self.engine.vfo + self.step, snap=True)),
            ("Ctrl+Left", lambda: self.tune(self.engine.vfo - self.step, snap=True)),
            ("Ctrl+Up", lambda: self.tune(self.engine.vfo + 10 * self.step, snap=True)),
            ("Ctrl+Down", lambda: self.tune(self.engine.vfo - 10 * self.step, snap=True)),
            ("Ctrl+Shift+M", lambda: self.audio_panel.mute.toggle()),
            ("Alt+O", lambda: self.choose_mode("AUTO")),
            ("Alt+Left", lambda: self.jump_neighbor(-1)), ("Alt+Right", lambda: self.jump_neighbor(+1)),
            ("Ctrl+B", lambda: self._vfo_action("swap")),
            ("Ctrl+S", self._auto_squelch),
            ("Ctrl+L", self._auto_levels),
            ("Ctrl+E", self._center_waterfall),
            ("Escape", self._escape),
        ):
            QShortcut(QKeySequence(keys), self, activated=fn)

    # ================================================================== fonte
    def start_source(self, opts: dict):
        self._stop_sonde()
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
            self._set_running_ui(False)
            if self._quiet_start:  # reconexão ao abrir: avisa sem diálogo
                self._quiet_error = str(e)
                return
            if name == "RTL-SDR":
                from ..sources import rtl_driver
                need, reason, _pid = rtl_driver.needs_preparation()
                if need and QMessageBox.question(
                        self, "RTL-SDR", f"{e}\n\n{reason}\nInstalar agora o driver WinUSB (como o Zadig)?") \
                        == QMessageBox.Yes:
                    ok, msg = rtl_driver.prepare()
                    QMessageBox.information(self, "Preparar RTL-SDR",
                                            msg + ("\n\nReconecte o dongle e clique em Ligar." if ok else ""))
                    return
            text = str(e)
            if name == "RTL-SDR" and sys.platform == "win32":
                from ..sources import rtl_driver
                ifaces = rtl_driver.windows_interfaces()
                if ifaces:
                    text += "\n\nDriver no Windows: " + "; ".join(
                        f"interface {'—' if i.mi is None else i.mi}: {i.service or 'nenhum'}" for i in ifaces)
            QMessageBox.warning(self, "Fonte de sinal", text)
            return
        self.cfg.update(source=name, sample_rate=src.sample_rate, gain=opts["gain"], ppm=opts["ppm"])
        if src.check_freq(self.engine.vfo):  # frequência salva fora do alcance deste dongle
            self.statusBar().showMessage(src.check_freq(self.engine.vfo), 12000)
            self.engine.vfo = 145.570e6
            self.vfos[self.active_vfo]["freq"] = self.engine.vfo
        self.engine.start(src)
        self._apply_receiver_settings()
        self._set_running_ui(True)
        tuner = getattr(src, "tuner", "")
        if getattr(src, "library", ""):
            tuner += f" · biblioteca {src.library}"
        self.rx_panel.info.setText(f"{src.name} {tuner} — {src.sample_rate / 1e6:g} MS/s, bloco {src.block_size}")
        self.status_src.setText(f"● {src.name} {src.sample_rate / 1e6:g} MS/s")
        self.hdr_summary.setText(f"● {src.name} {tuner} — {src.sample_rate / 1e6:g} MS/s")
        self.cfg.update(device_index=opts.get("device_index", 0), device_name=self.rx_panel.device.currentText())
        if name in ("RTL-SDR", "rtl_tcp", "SoapySDR"):
            self.cfg["rx_ever_connected"] = True
        self._update_lcd()

    def stop_source(self):
        self._stop_sonde()
        self._stop_scan()
        self._sscan_stop()
        self.engine.stop()
        self._set_running_ui(False)
        self.rx_panel.info.setText("Parado")
        self.status_src.setText("Parado")
        self.audio_panel.rec_audio.setChecked(False)
        self.audio_panel.rec_iq.setChecked(False)
        self._refresh_band_keys()

    def _prepare_rtlsdr(self):
        from ..sources import rtl_driver
        need, reason, _pid = rtl_driver.needs_preparation()
        if not need:
            QMessageBox.information(self, "RTL-SDR", "Nada a preparar: nenhum RTL-SDR sem o driver WinUSB foi "
                                    "encontrado. Conecte o dongle e tente de novo, se necessário.")
            return
        if QMessageBox.question(self, "Preparar RTL-SDR", f"{reason}\n\nInstalar o driver WinUSB somente na "
                                "interface 0 do dongle? O Windows pedirá permissão de administrador uma vez.") \
                != QMessageBox.Yes:
            return
        ok, msg = rtl_driver.prepare()
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Preparar RTL-SDR",
                                                                 msg + ("\n\nReconecte o dongle e clique em Ligar." if ok else ""))

    def _diagnose_rtlsdr(self):
        from ..sources import rtl_driver
        QMessageBox.information(self, "Diagnóstico do RTL-SDR", rtl_driver.diagnose())

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
        if not self._freq_supported(freq):
            return False
        self.engine.tune(freq)
        self.vfos[self.active_vfo]["freq"] = freq
        self.cfg["vfo_freq" if self.active_vfo == "A" else "vfo_b_freq"] = freq
        if self.current_mem and abs(self.current_mem.freq - freq) > 1:
            self.current_mem = None
        self._sync_views()

    def _freq_supported(self, freq: float) -> bool:
        """Recusa (com aviso, sem travar) frequências que o dongle não alcança."""
        src = self.engine.source
        fs = self.engine.sample_rate
        if src is None or abs(freq - src.center_freq) < fs / 2 * 0.9:
            return True
        problem = src.check_freq(freq + fs / 8)
        if not problem:
            return True
        self.statusBar().showMessage(problem, 12000)
        box = QMessageBox(QMessageBox.Information, "Frequência fora do alcance", problem, QMessageBox.Ok, self)
        box.setModal(False)
        box.show()
        self._sync_views()
        return False

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

    def _show_initial_receiver_setup(self):
        """Leva o usuário às configurações na primeira utilização sem receptor configurado."""
        if self.engine.running or self._presenting or self.rx_panel.source.currentText() != "RTL-SDR":
            return
        self.tabs.setCurrentWidget(self.pages["settings"])
        self.settings_tabs.setCurrentIndex(0)
        self.rx_panel.refresh_devices()
        available = any(self.rx_panel.device.itemText(i)[:1].isdigit()
                        for i in range(self.rx_panel.device.count()))
        msg = ("Selecione o SDR, configure a taxa e clique em Ligar." if available else
               "Nenhum RTL-SDR detectado: conecte-o e use Ajuda → Preparar RTL-SDR / Diagnóstico.")
        self.rx_panel.info.setText(msg)
        self.statusBar().showMessage(msg, 18000)

    def _band_unsupported(self, band):
        mid = (band.start + band.end) / 2
        src = self.engine.source
        if src is not None:
            return src.check_freq(mid) or ""
        if self.cfg.get("source") == "RTL-SDR" and self.cfg.get("device_name"):
            from ..sources.rtlsdr_source import tuning_range
            device = self.cfg.get("device_name", "")
            v4 = "V4" in device.upper()
            low, high = tuning_range("R828D" if v4 else "R820T", v4,
                                     int(self.cfg.get("direct_sampling", 0)), device)
            if not low <= mid <= high:
                return (f"{band.name}: fora da faixa do último SDR ({low / 1e6:g}–"
                        f"{high / 1e6:g} MHz). Verifique a amostragem direta ou o dispositivo.")
        return ""

    def _refresh_band_keys(self):
        if not hasattr(self, "band_bar"):
            return
        reasons = {b.name: self._band_unsupported(b) for b in self.band_bar.bands}
        self.band_bar.refresh(self.engine.vfo, reasons)

    def _analog_display_changed(self, on, style):
        self.cfg["analog_enabled"] = bool(on)
        self.cfg["analog_style"] = style
        self.analog_panel.set_style(style)
        self.analog_panel.setVisible(bool(on))
        self.cfg.save()

    def _set_visible_bands(self, names):
        """Atualiza as teclas sem reiniciar e preserva a seleção do operador."""
        self.cfg["bands_visible"] = list(names)
        old = self.band_bar
        new = BandKeys(names)
        new.selected.connect(self._band_button)
        self.lcd.attach_band_keys(new)
        old.deleteLater()
        self.band_bar = new
        self._refresh_band_keys()

    def _band_button(self, band):
        reason = self._band_unsupported(band)
        if reason:
            self.statusBar().showMessage(reason, 12000)
            return
        self._goto_band(band)

    def _remember_current_band(self):
        band = band_for(self.engine.vfo)
        if band is None:
            return
        stacks = self.cfg.setdefault("band_stacks", {})
        history = stacks.setdefault(band.name, [])
        entry = {"freq": float(self.engine.vfo), "mode": self.mode}
        history[:] = [entry] + [x for x in history
                                if abs(x.get("freq", 0) - entry["freq"]) >= max(1000, band.step * 2)
                                or x.get("mode") != entry["mode"]][:2]

    def _goto_band(self, band):
        reason = self._band_unsupported(band)
        if reason:
            self.statusBar().showMessage(reason, 12000)
            return
        current = band_for(self.engine.vfo)
        same_band = current is not None and current.name == band.name
        self._remember_current_band()
        history = self.cfg.get("band_stacks", {}).get(band.name, [])
        if same_band and len(history) > 1:
            next_entry = history.pop(1)
            history.insert(0, next_entry)
        elif history:
            next_entry = history[0]
        else:
            next_entry = {"freq": (band.start + band.end) / 2, "mode": band.mode}
        freq = float(next_entry["freq"])
        if not band.start <= freq <= band.end or not self._freq_supported(freq):
            return
        self.set_step(band.step)
        self.set_mode(next_entry["mode"])
        self.tune(freq, snap=True)


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

    def _vox_ready(self) -> bool:
        """VOX precisa de squelch: com o squelch aberto tudo seria gravado."""
        if self.audio_panel.squelch.value() > -150 or self.engine.tone_squelch is not None:
            return True
        r = QMessageBox.question(self, "VOX", "O squelch está aberto: o VOX gravaria o ruído o tempo todo.\n\n"
                                 "Ajustar o squelch automaticamente (6 dB acima do ruído atual)?")
        if r == QMessageBox.Yes:
            self._auto_squelch()
            return True
        return False

    def _record_audio(self, on):
        ap = self.audio_panel
        if on:
            if not self.engine.running:
                ap.rec_audio.setChecked(False)
                return
            if ap.vox.isChecked():
                if not self._vox_ready():
                    ap.rec_audio.setChecked(False)
                    return
                folder = str(Path(self.cfg["recordings_dir"]) / "vox")
                single = bool(ap.vox_files.currentData())
                self.engine.vox_rec = ActivityRecorder(folder, AUDIO_RATE, min_s=0.5, single_file=single)
                self.statusBar().showMessage(f"Gravando com VOX em {folder}", 6000)
            else:
                p = self.engine.start_audio_recording(self.cfg["recordings_dir"])
                self.statusBar().showMessage(f"Gravando áudio em {p}", 5000)
        else:
            rec, self.engine.vox_rec = self.engine.vox_rec, None
            if rec is not None:
                ev = rec.close()
                if ev:
                    self.scan_panel.add_activity(ev, self._mem_name(ev["freq"]))
            self.engine.stop_audio_recording()
        self._rec_flag()

    def _record_iq(self, on):
        if on:
            if not self.engine.running:
                self.audio_panel.rec_iq.setChecked(False)
                return
            vox = self.audio_panel.vox.isChecked()
            if vox and not self._vox_ready():
                self.audio_panel.rec_iq.setChecked(False)
                return
            self.engine.iq_vox = vox
            p = self.engine.start_iq_recording(self.cfg["recordings_dir"])
            self.statusBar().showMessage(f"Gravando IQ{' (VOX)' if vox else ''} em {p}", 5000)
        else:
            self.engine.stop_iq_recording()
        self._rec_flag()

    def _rec_flag_vox(self):
        self.lcd.flags["VOX"] = self.audio_panel.vox.isChecked()

    def _rec_flag(self):
        self._rec_flag_vox()
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
        self._after_select()

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

    # ================================================================== anúncio / OTA
    def _startup_notices(self):
        from .assist_panels import show_welcome
        show_welcome(self)
        self.updates.show_last_result()

    def operation_busy(self) -> str:
        """Motivo para adiar a atualização automática, ou '' se o programa está livre."""
        e = self.engine
        if e.recording_audio or e.recording_iq or e.vox_rec is not None:
            return "gravação em andamento"
        if e.activity_rec is not None and e.activity_rec.active:
            return "gravando uma transmissão"
        if self.sscan is not None and self.sscan.running:
            return "scanner em andamento"
        if self.scan is not None:
            return "varredura de memórias"
        if e.replay_pos is not None:
            return "reproduzindo (voltar no tempo)"
        from PySide6.QtWidgets import QApplication
        if QApplication.activeModalWidget() is not None:
            return "janela de diálogo aberta"
        return ""

    def quit_for_update(self):
        """Fecha tudo para o auxiliar externo instalar a atualização (ele reabre o programa)."""
        self._quitting_for_update = True
        self.close()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
        QTimer.singleShot(8000, lambda: os._exit(0))

    # ================================================================== Sondas RS41 / IQ original
    def _start_sonde(self, freq, fsk_path, rs41_path):
        """Usa o mesmo fluxo IQ que alimenta o waterfall, sem reabrir o SDR."""
        from ..sonde_rx import RS41Receiver
        self._stop_sonde()
        if not self.engine.running or self.engine.source is None:
            self.sonde_panel.status.setText("Ligue primeiro o receptor SDR. O waterfall isolado não decodifica.")
            return
        if not self._freq_supported(freq):
            self.sonde_panel.status.setText("A frequência está fora do alcance do dispositivo.")
            return
        if self.cfg.get("source") == "Simulador":
            self.sonde_panel.status.setText("Selecione um receptor físico ou um arquivo IQ gravado.")
            return
        self.tune(freq)
        worker = RS41Receiver(
            int(self.engine.sample_rate), freq,
            on_decoded=lambda track, raw: self.engine.events.put(("sonde_rx", (track, raw), time.time())),
            on_status=lambda msg: self.engine.events.put(("sonde_status", msg, time.time())),
            on_frame=lambda raw: self.engine.events.put(("sonde_frame", raw, time.time())),
            fsk_path=fsk_path, decoder_path=rs41_path,
        )
        try:
            worker.start()
        except (OSError, ValueError, RuntimeError) as exc:
            self.sonde_panel.status.setText(f"Não foi possível iniciar RS41: {exc}")
            worker.stop()
            return
        self.sonde_worker = worker
        self.engine.iq_listeners.append(worker.feed)
        self.sonde_panel.running(True)

    def _capture_sonde_iq(self, filename):
        worker = getattr(self, "sonde_worker", None)
        if worker is None:
            self.sonde_panel.status.setText("Ligue a recepção RS41 antes de gravar IQ.")
            return
        try:
            worker.start_capture(filename, 20)
            self.sonde_panel.status.setText("Gravando 20 s de IQ complexo a 48 kS/s…")
        except (OSError, RuntimeError) as exc:
            self.sonde_panel.status.setText(f"Erro ao gravar IQ: {exc}")

    def _stop_sonde(self):
        worker = getattr(self, "sonde_worker", None)
        if worker is not None:
            try:
                self.engine.iq_listeners.remove(worker.feed)
            except ValueError:
                pass
            worker.stop()
            self.sonde_worker = None
        if hasattr(self, "sonde_panel"):
            self.sonde_panel.running(False)

    # ================================================================== CAT · Hamlib
    def _cat_received(self, freq: float, mode: str):
        """Sincronização de recepção somente, sem PTT nem transmissão."""
        if not 24_000 <= freq <= 1_766_000_000:
            self.rigctl_panel.status.setText("CAT: frequência fora da faixa do SDR Tool")
            return
        if not self._freq_supported(freq):
            self.rigctl_panel.status.setText("CAT: o receptor SDR não suporta esta frequência")
            return
        if mode and mode in MODES:
            self.set_mode(mode)
        self.tune(freq)

    # ================================================================== configurações / web
    def _setting_changed(self, key, value):
        self.cfg[key] = value
        if key == "rtl_library":
            from ..sources.rtlsdr_source import set_preference
            set_preference(value)
        if key == "ui_level":
            self.apply_level(value)
        elif key == "lcd_theme":
            self.lcd_theme.setCurrentText(value)
        elif key == "auto_tune":
            self._set_auto_tune(bool(value))
        elif key == "my_locator":
            self.dec_panel.locator.setText(value)
        self.cfg.save()

    def _web_apply(self):
        from ..webserver import WebServer
        sp = self.settings_panel
        self.cfg.update(web_enabled=sp.web_on.isChecked(), web_allow_lan=sp.web_lan.isChecked(),
                        web_require_key=sp.web_key.isChecked(), web_port=sp.web_port.value())
        if self.web is not None:
            if self.web.audio.push in self.engine.audio_listeners:
                self.engine.audio_listeners.remove(self.web.audio.push)
            self.web.stop()
            self.web = None
        if not sp.web_on.isChecked():
            sp.web_status.setText("Interface web desativada")
            return
        eng = self.engine
        web = WebServer(lambda: self._web_state,
                        lambda: (eng.spectrum, eng.spectrum_center, eng.sample_rate) if eng.spectrum is not None else None,
                        lan=sp.web_lan.isChecked(), port=sp.web_port.value(),
                        require_key=sp.web_key.isChecked())
        try:
            web.start()
        except OSError as e:
            sp.web_status.setText(f"Não foi possível abrir a porta {sp.web_port.value()}: {e}")
            return
        self.web = web
        eng.audio_listeners.append(web.audio.push)
        local = web.url(False)
        txt = f"Ativa: {local}"
        if web.lan:
            txt += f"\nRede local: {web.url(True)}"
            if not web.require_key:
                txt += "\nSem chave: qualquer aparelho da rede local abre direto por este endereço."
        sp.web_status.setText(txt)

    def _web_open(self):
        if self.web is None:
            self.settings_panel.web_on.setChecked(True)
        if self.web is not None:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(self.web.url(False)))

    def _web_copy(self):
        if self.web is None:
            return
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.web.url())
        self.statusBar().showMessage("Endereço da interface web copiado", 4000)

    def _update_web_state(self):
        if self.web is None:
            return
        st = self.engine.status
        dbm, s_txt = dbfs_to_s_units(st["signal_db"], self.cfg["s_meter_cal"])
        self._web_state = {
            "version": __version__, "freq": self.engine.vfo, "mode": self.lcd.mode, "bw": self.high - self.low,
            "s_text": s_txt, "dbm": dbm, "sq_open": bool(st["sq_open"]),
            "ctcss": st.get("ctcss"), "mem": self.lcd.mem_label, "scan": bool(self.lcd.flags.get("SCAN")),
            "replay": bool(self.lcd.flags.get("REPLAY")), "running": self.engine.running,
            "aprs": list(self._web_aprs)}

    # ================================================================== modo AUTO / auto-sintonia / vizinho
    def choose_mode(self, mode: str):
        """Tecla de modo (display, painel ou atalho). "AUTO" detecta e aplica sozinho."""
        if mode == "AUTO":
            self.auto_mode = True
            self.cfg["auto_mode"] = True
            self._sync_views()
            self._after_select()
            return
        self.auto_mode = False
        self.cfg["auto_mode"] = False
        self.set_mode(mode)

    def _set_auto_tune(self, on: bool):
        self.auto_tune = bool(on)
        self.cfg["auto_tune"] = self.auto_tune
        self.statusBar().showMessage("Auto-sintonia ao selecionar: " + ("ligada" if on else "desligada"), 4000)
        self._sync_views()

    def select_transmission(self, freq: float):
        """Clique no waterfall/espectro: sintoniza e, se ligado, ajusta exatamente na transmissão."""
        if self.tune(freq) is not False:
            self._after_select()

    def _after_select(self, from_scanner: bool = False):
        if not self.engine.running or not (self.auto_mode or self.auto_tune):
            return
        self._sel_gen += 1
        gen = self._sel_gen
        vfo, mode, step = self.engine.vfo, self.mode, self.step
        if self.auto_mode:
            from ..dsp.assist import detect_mode
            kind, secs = "auto_mode", 2.5
            fn = lambda iq, fs, v, m: detect_mode(iq, fs, v)  # noqa: E731
        else:
            from ..dsp.assist import fine_tune
            kind, secs = "auto_tune", (4.0 if mode in ("USB", "LSB") else 0.6)
            fn = lambda iq, fs, v, m: fine_tune(iq, fs, m, v, step)  # noqa: E731

        def cb(iq, fs):
            try:
                res = fn(iq, fs, vfo, mode)
            except Exception as e:  # noqa: BLE001
                log.warning("auto: %s", e)
                res = None
            self.engine.events.put((kind, {"res": res, "vfo": vfo, "gen": gen}, time.time()))
        QTimer.singleShot(250, lambda: self.engine.capture_if(secs, cb) if gen == self._sel_gen else None)

    def _auto_result(self, kind, d):
        if d["gen"] != self._sel_gen or abs(self.engine.vfo - d["vfo"]) > 1:
            return  # outra seleção aconteceu no meio da análise
        res = d["res"]
        if res is None:
            return
        if kind == "auto_mode":
            if res.confidence < 0.55:
                return
            grid = {"CW": 10, "USB": 1, "LSB": 1}.get(res.mode, 100)
            target = round((d["vfo"] + res.center_offset) / grid) * grid
            if res.mode != self.mode:
                self.set_mode(res.mode, res.bandwidth)
            self.tune(target)
            self.statusBar().showMessage(f"AUTO: {res.mode} — {res.reason}", 6000)
            if res.mode in ("NFM", "WFM", "AM") and self.auto_tune:
                self._after_select_tune_only()
        else:
            delta, why = res
            if abs(delta) < (2 if self.mode in ("USB", "LSB", "CW") else 20):
                return
            self.tune(d["vfo"] + delta)
            self.statusBar().showMessage(f"Auto-sintonia: {delta:+.0f} Hz ({why})", 6000)

    def _after_select_tune_only(self):
        was = self.auto_mode
        self.auto_mode = False
        try:
            self._after_select()
        finally:
            self.auto_mode = was

    def _pan_to(self, center: float):
        """Arraste do waterfall: o receptor passa a cobrir a região visível (o VFO anda junto)."""
        eng = self.engine
        if not eng.running or eng.hold_center or not eng.source.tunable:
            return
        problem = eng.source.check_freq(center)
        if problem:
            self.statusBar().showMessage(problem, 8000)
            return
        delta = center - eng.source.center_freq
        if self.tune(eng.vfo + delta) is False:
            return
        eng.set_center(center)
        self.statusBar().showMessage(f"Waterfall: região {center / 1e6:.3f} MHz", 3000)

    def jump_neighbor(self, direction: int):
        """◀ / ▶: salta para a próxima transmissão ativa e sintoniza nela."""
        if not self.engine.running or self.engine.spectrum is None:
            self.statusBar().showMessage("Ligue o receptor para procurar transmissões.", 4000)
            return
        from ..scanner import detect_signals
        src, fs = self.engine.source, self.engine.sample_rate
        center = self.engine.spectrum_center
        if abs(center - src.center_freq) > 1:  # espectro ainda é do centro anterior: espera o novo
            QTimer.singleShot(150, lambda: self.jump_neighbor(direction))
            return
        vfo = self.engine.vfo
        res = max(500, min(self.step, 5000))
        dets, _floor = detect_signals(self.engine.spectrum, center, fs, center - fs / 2, center + fs / 2, res, 10)
        sep = max((self.high - self.low) * 0.6, 1500)
        locks = self.sscan.cfg.lockouts if self.sscan is not None else set()
        cands = [d.freq for d in dets if (d.freq - vfo) * direction > sep
                 and not any(abs(d.freq - x) < sep for x in locks)]
        if cands:
            self._neighbor_hops = 0
            target = min(cands, key=lambda f: abs(f - vfo))
            self.select_transmission(target)
            self.statusBar().showMessage(f"Transmissão vizinha: {target / 1e6:.5f} MHz", 4000)
            return
        if self._neighbor_hops >= 20:
            self._neighbor_hops = 0
            self.statusBar().showMessage("Nenhuma transmissão encontrada nessa direção.", 5000)
            return
        self._neighbor_hops += 1
        nxt = vfo + direction * fs * 0.4
        self.statusBar().showMessage(f"Procurando transmissão… {nxt / 1e6:.3f} MHz", 2000)
        if self.tune(nxt) is False:
            self._neighbor_hops = 0
            return
        QTimer.singleShot(700, lambda: self.jump_neighbor(direction))

    # ================================================================== assistente de sintonia
    def _assist_capture(self, seconds, kind, fn, busy_text, manual=True):
        if not self.engine.running:
            if manual:
                QMessageBox.information(self, "Assistente", "Ligue o receptor primeiro.")
            return False
        if self._assist_busy:
            return False
        self._assist_busy = True
        if manual:
            self.assist.busy(busy_text)
        vfo, mode = self.engine.vfo, self.mode

        def cb(iq, fs):
            try:
                res = fn(iq, fs, vfo, mode)
            except Exception as e:  # noqa: BLE001
                log.exception("assistente: %s", e)
                res = None
            self.engine.events.put((kind, {"res": res, "vfo": vfo, "mode": mode, "manual": manual}, time.time()))
        self.engine.capture_if(seconds, cb)
        return True

    def _assist_autotune(self, manual=True):
        if self.mode not in ("USB", "LSB"):
            if manual:
                self.assist.result.setText("A auto-sintonia funciona em USB ou LSB. Use \"Detectar modo\" antes.")
            return
        from ..dsp.assist import estimate_ssb_offset
        self._assist_capture(4.0, "assist_tune", lambda iq, fs, v, m: estimate_ssb_offset(iq, fs, m),
                             "Ouvindo a fonia por 4 s…", manual)

    def _assist_detect(self):
        from ..dsp.assist import detect_mode
        self._assist_capture(3.0, "assist_mode", lambda iq, fs, v, m: detect_mode(iq, fs, v),
                             "Analisando o sinal por 3 s…")

    def _assist_filter(self):
        from ..dsp.assist import adaptive_passband
        low, high = self.low, self.high
        self._assist_capture(1.0, "assist_filter", lambda iq, fs, v, m: adaptive_passband(iq, fs, m, low, high),
                             "Medindo a largura do sinal…")

    def _assist_result(self, kind, d):
        self._assist_busy = False
        res, manual = d["res"], d["manual"]
        if abs(self.engine.vfo - d["vfo"]) > 1:  # usuário mudou de frequência no meio
            self.assist.done("Frequência alterada durante a análise; tente de novo.")
            return
        if kind == "assist_tune":
            if res is None:
                if manual:
                    self.assist.done("Não encontrei voz SSB suficiente. Tente com o sinal no ar.")
                return
            delta, conf = res
            if not manual and (abs(delta) < 8 or conf < 0.3):
                return
            self.tune(d["vfo"] + delta)
            self.assist.done(f"Corrigido {delta:+.0f} Hz (confiança {conf * 100:.0f}%).")
        elif kind == "assist_mode":
            if res is None:
                self.assist.done("Nenhum sinal claro perto da frequência atual.")
                return
            self.set_mode(res.mode, res.bandwidth)
            grid = {"CW": 10, "USB": 1, "LSB": 1}.get(res.mode, 100)
            self.tune(round((d["vfo"] + res.center_offset) / grid) * grid)
            self.assist.done(f"{res.mode} — {res.reason} (confiança {res.confidence * 100:.0f}%).")
        else:
            if res is None:
                self.assist.done("Não consegui medir o sinal.")
                return
            self._set_passband(*res)
            self.assist.done(f"Filtro ajustado: {res[0]:+.0f} a {res[1]:+.0f} Hz ({(res[1] - res[0]) / 1e3:.1f} kHz).")

    # ================================================================== voltar no tempo
    def _set_timeshift(self, seconds):
        self.cfg["timeshift_s"] = seconds
        self.engine.timeshift_seconds = seconds
        if self.engine.running:
            self.engine.set_timeshift(seconds)
        self.tshift.status.setText("Desligado" if seconds <= 0 else "Ao vivo")

    def _replay(self, seconds):
        ts = self.engine.timeshift
        if not self.engine.running or ts is None:
            QMessageBox.information(self, "Voltar no tempo", "Ligue o receptor e escolha o tamanho do buffer.")
            return
        if ts.available_seconds < 1:
            return
        self.engine.start_replay(min(seconds, ts.available_seconds - 0.5))

    # ================================================================== receptores extras
    def _extra_add(self):
        if not self.engine.running:
            QMessageBox.information(self, "Receptores extras", "Ligue o receptor primeiro.")
            return
        ex = self.engine.add_extra(self.engine.vfo, self.mode, self.high - self.low)
        if ex is not None:
            self.extras_panel.add_row(ex)
            self._extra_markers()

    def _extra_remove(self, ex):
        self.engine.remove_extra(ex)
        self.extras_panel.remove_row(ex)
        self._extra_markers()

    def _extra_markers(self):
        self.wf.set_extras([row["ex"].freq for row in self.extras_panel.rows if row["ex"].enabled])

    # ================================================================== transcrição
    def _toggle_live_captions(self, on):
        """Fonia ao vivo: processamento no CPU em worker, jamais na thread DSP."""
        from ..transcribe import backend_available
        from ..live_caption import LiveCaptionWorker
        if on:
            if not backend_available():
                self.live_btn.blockSignals(True)
                self.live_btn.setChecked(False)
                self.live_btn.blockSignals(False)
                QMessageBox.information(
                    self, "Legendas locais", "O recurso exige faster-whisper e um modelo local."
                    "\nInstale a dependência e deixe o modelo disponível antes de ativar."
                    "\nA primeira utilização do backend pode baixar o modelo.")
                return
            self.caption_worker = LiveCaptionWorker(
                on_result=lambda *args: self.engine.events.put(("live_caption", args, time.time())),
                on_error=lambda msg: self.engine.events.put(("caption_error", msg, time.time())),
                model_size=self.live_captions_panel.model.currentData(),
                language=self.live_captions_panel.language.currentData(),
                meta_provider=lambda: (float(self.engine.vfo), str(self.mode)),
            )
            self.engine.audio_listeners.append(self.caption_worker.feed)
            self.caption_label.setText("Legendas locais ativadas — aguardando fonia…")
            self.caption_label.setVisible(True)
            self.cfg["live_caption_enabled"] = True
        else:
            if self.caption_worker is not None:
                callback = self.caption_worker.feed
                try:
                    self.engine.audio_listeners.remove(callback)
                except ValueError:
                    pass
                self.caption_worker.stop()
                self.caption_worker = None
            self.cfg["live_caption_enabled"] = False
            self.caption_label.setVisible(False)

    def _toggle_transcription(self, on):
        from ..transcribe import Transcriber, backend_available
        if on and self.transcriber is None:
            if not backend_available():
                self.scan_panel.transcribe.setChecked(False)
                QMessageBox.information(self, "Transcrição", (
                    "A transcrição local usa o pacote opcional faster-whisper (o áudio não sai do computador).\n"
                    "Instale com:  pip install faster-whisper\n"
                    "Na primeira vez o modelo (~500 MB) é baixado automaticamente."))
                return
            self.transcriber = Transcriber(
                lambda p, t, c: self.engine.events.put(("transcription", (p, t, c), time.time())))
        elif not on and self.transcriber is not None:
            self.transcriber.stop()
            self.transcriber = None

    # ================================================================== waterfall
    def _levels(self):
        lo, hi = self.wf_min.value(), self.wf_max.value()
        self.wf.set_levels(lo, hi)
        self.cfg["wf_min_db"], self.cfg["wf_max_db"] = lo, hi

    def _weak_signal_toggled(self, enabled):
        """Perfil reversível para redução de interferências, sem chamar de rede neural."""
        ap = self.audio_panel
        if enabled:
            self._weak_restore = {
                "nb": ap.nb.isChecked(), "nr": ap.nr.isChecked(),
                "nr_str": ap.nr_str.value(), "agc": ap.agc.isChecked(),
                "agc_speed": ap.agc_speed.currentText(),
            }
            ap.nb.setChecked(True)
            ap.nr.setChecked(True)
            ap.nr_str.setValue(max(ap.nr_str.value(), 24))
            ap.agc.setChecked(True)
            ap.agc_speed.setCurrentText("Lento")
            self.statusBar().showMessage("Sinal fraco: NB/NR/AGC aplicados (DSP, sem IA neural)", 6000)
        elif self._weak_restore is not None:
            saved = self._weak_restore
            self._weak_restore = None
            ap.nb.setChecked(saved["nb"])
            ap.nr.setChecked(saved["nr"])
            ap.nr_str.setValue(saved["nr_str"])
            ap.agc.setChecked(saved["agc"])
            ap.agc_speed.setCurrentText(saved["agc_speed"])
            self.statusBar().showMessage("Perfil de sinal fraco desativado; ajustes anteriores restaurados", 6000)

    def _auto_levels(self):
        r = self.wf.auto_levels()
        if r:
            for s, v in ((self.wf_min, r[0]), (self.wf_max, r[1])):
                s.blockSignals(True)
                s.setValue(int(v))
                s.blockSignals(False)
            self.cfg["wf_min_db"], self.cfg["wf_max_db"] = r

    # ================================================================== atualização
    def _toggle_keep_center(self, checked):
        self.cfg["wf_keep_vfo_centered"] = bool(checked)
        if checked:
            self._center_waterfall()

    def _center_waterfall(self):
        """Recentraliza no VFO preservando a escala horizontal do espectro."""
        eng = self.engine
        src = eng.source
        if src is not None and getattr(src, "tunable", False) and not eng.hold_center:
            if abs(eng.vfo - src.center_freq) > eng.sample_rate * 0.4:
                error = src.check_freq(eng.vfo)
                if error:
                    self.statusBar().showMessage(error, 10000)
                    return
                eng.set_center(eng.vfo)
        self.wf.center_on_vfo()

    def _sync_views(self):
        vfo = self.engine.vfo
        self.wf.step = self.step
        self.wf.set_vfo(vfo, self.low, self.high)
        if self.cfg.get("wf_keep_vfo_centered", False):
            self.wf.center_on_vfo()
        self.mode_panel.show_mode(self.mode, self.high - self.low, self.step)
        self._update_lcd()

    def _update_lcd(self):
        self.fav_bar.mark_current(self.engine.vfo)
        lcd = self.lcd
        lcd.set_freq(self.engine.vfo)
        lcd.mode = f"AUTO·{self.mode}" if self.auto_mode else self.mode
        lcd.mode_key = "AUTO" if self.auto_mode else self.mode
        lcd.auto_tune = self.auto_tune
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
        self._refresh_band_keys()
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
                    if ev[0] == "hit":
                        self.occupancy.record(ev[1].freq, time.time())
                    if ev[0] == "listen":
                        self.statusBar().showMessage(f"Scanner: sinal em {ev[1] / 1e6:.4f} MHz "
                                                     f"{self._mem_name(ev[1])}", 4000)
                        self._sync_views()
                        self._after_select(from_scanner=True)
                    elif ev[0] == "resume":
                        self._sync_views()
            self._update_hits()
            if (self.scan_panel.tabs.currentWidget() is self.occupancy_panel
                    and now - self._last_occupancy_refresh > 4):
                self.occupancy_panel.refresh()
                self._last_occupancy_refresh = now
            self.occupancy.flush()
        for spec, center, fs in lines[-8:]:
            self.wf.add_line(spec, center, fs)
        if lines and abs(getattr(self, "_marker_center", 0) - eng.center_freq) > 1:
            self._refresh_markers()
            self.wf.set_vfo(eng.vfo, self.low, self.high)

        st = eng.status
        if eng.running:
            fresh = time.monotonic() - st.get("signal_sample_time", 0) < 2.5
            raw_db = st.get("signal_db", -150.0)
            if fresh and math.isfinite(float(raw_db)):
                dbm, s = dbfs_to_s_units(raw_db, self.cfg["s_meter_cal"])
                self.lcd.set_signal(dbm, s, st["sq_open"] and self.audio_panel.squelch.value() > -150)
                self.lcd.setToolTip(f"S-meter: {raw_db:.1f} dBFS · {dbm:.1f} dBm aprox. · {s}")
            else:
                dbm = -147.0
                self.lcd.set_signal(None, "S--", False)
                self.lcd.setToolTip("S-meter: sem amostras IQ recentes")
            if self.cfg.get("analog_enabled", False):
                self.analog_panel.set_readings(dbm, st.get("audio_level", 0.0))
            if getattr(self, "_sq_collect", False):
                self._sq_samples.append(st["signal_db"])
            tone = st.get("ctcss")
            self.lcd.ctcss_text = f"CTCSS {tone:.1f}" if tone else ""
            self.dec_panel.set_ctcss(tone)
            self.status_cpu.setText(f"DSP {st['cpu'] * 100:4.0f}%  perdas {st['dropped']}  "
                                    f"centro {eng.center_freq / 1e6:.4f} MHz")
        elif self.rx_panel.start_btn.isChecked():
            self.stop_source()
        elif not eng.running and self.lcd.signal_valid:
            self.lcd.set_signal(None, "S--", False)

        if self.sonde_worker is not None:
            now = time.monotonic()
            if now - getattr(self, "_sonde_diag_time", 0.0) > 2.0:
                self._sonde_diag_time = now
                self.sonde_panel.update_diagnostics(self.sonde_worker.diagnostics())
        n = 0
        while not eng.events.empty() and n < 50:
            kind, data, ts = eng.events.get_nowait()
            n += 1
            if kind == "aprs":
                self.dec_panel.add_aprs(data, ts)
                self._web_aprs.appendleft({"t": time.strftime("%H:%M:%S", time.localtime(ts)), "src": data.source,
                                           "type": data.type, "pos": data.position_str(),
                                           "text": (data.comment or data.message or "")[:80]})
                self.statusBar().showMessage(f"APRS: {data.raw}", 4000)
            elif kind == "sonde_rx":
                track, _raw = data
                self.sonde_panel.add_record(track)
                self.sonde_feed.add_live_record(track)
                self.sonde_panel.status.setText(
                    f"RS41: {track.ident} · altitude {track.altitude_m} m · "
                    f"{self.sonde_worker.received if self.sonde_worker else 0} quadros")
            elif kind == "sonde_status":
                self.sonde_panel.status.setText(str(data))
            elif kind == "sonde_frame":
                self.sonde_panel.add_frame(data)
            elif kind == "dtmf":
                self.dec_panel.add_dtmf(data, ts)
            elif kind == "vox":
                self.scan_panel.add_activity(data, self._mem_name(data["freq"]))
            elif kind == "activity":
                self.scan_panel.add_activity(data, self._mem_name(data["freq"]))
                if self.transcriber is not None:
                    self.transcriber.submit(data["file"])
            elif kind == "transcription":
                self.scan_panel.set_transcription(*data)
            elif kind == "live_caption":
                stamp, recognized, calls, lang, meta = data
                freq, mode = meta if meta is not None else (eng.vfo, self.mode)
                self.live_captions_panel.add_caption(stamp, recognized, calls, lang, freq, mode)
                self.caption_label.setText(f"{freq / 1e6:.5f} MHz · {mode}: {recognized}")
                self._live_caption_last = stamp
            elif kind == "caption_error":
                self.caption_label.setText(f"Legendas: {data}")
                self.statusBar().showMessage(f"Transcrição local: {data}", 10000)
            elif kind in ("auto_mode", "auto_tune"):
                self._auto_result(kind, data)
            elif kind in ("assist_tune", "assist_mode", "assist_filter"):
                self._assist_result(kind, data)
            elif kind == "replay":
                self.lcd.flags["REPLAY"] = True
            elif kind == "replay_end":
                self.lcd.flags["REPLAY"] = False
                self.tshift.status.setText("Ao vivo")
            elif kind == "source_msg":
                self.statusBar().showMessage(data, 10000)
                self.rx_panel.info.setText(data)
            elif kind == "error":
                self.statusBar().showMessage(data, 8000)
        self._scan_tick()
        self._update_web_state()
        if self.engine.replay_pos is not None:
            self.tshift.status.setText(f"Reproduzindo {self.engine.replay_seconds_behind():.0f} s atrás — "
                                       "a recepção ao vivo continua no waterfall")
        if self.extras_panel.rows and int(time.monotonic() * 2) % 2 == 0:
            self.extras_panel.refresh_levels()

    # ================================================================== layout / saída
    def _restore_layout(self):
        s = QSettings("PT2VHF", "SDRTool")
        geo, split = s.value("geometry"), s.value("split_v05")
        if isinstance(geo, QByteArray):
            self.restoreGeometry(geo)
        if isinstance(split, QByteArray):
            self.main_split.restoreState(split)
        self.audio_action.setChecked(s.value("audio_panel", "true") not in ("false", False))
        self.tabs.setCurrentIndex(0)

    def _reset_layout(self):
        if self._presenting:
            self.set_presentation(False)
        self.main_split.restoreState(self._default_split)
        self.audio_action.setChecked(True)
        self.tabs.setCurrentIndex(0)
        self.settings_tabs.setCurrentIndex(0)
        self.apply_level(self.cfg.get("ui_level", "Avançado"))

    # ================================================================== modo apresentação
    def set_presentation(self, on: bool):
        """Tela cheia de verdade (sem título nem barra de tarefas), no monitor em que a janela está."""
        on = bool(on)
        self.pres_action.setChecked(on)
        if on == self._presenting:
            return
        self._presenting = on
        self.cfg["presentation"] = on
        minimal = bool(self.cfg.get("presentation_minimal", True))
        if on:
            self._pres_was_max = self.isMaximized()
            self._pres_audio = self.audio_scroll.isVisible()
            if minimal:
                self.tabs.setCurrentIndex(0)
                for w in (self.menuBar(), self.statusBar(), self.header, self.tabs.tabBar(), self.audio_scroll,
                          self.fav_bar, self.wf_toolbar):
                    w.setVisible(False)
            self.showFullScreen()
            self.statusBar().showMessage("Modo apresentação — Esc ou F11 para sair", 6000)
        else:
            for w in (self.menuBar(), self.statusBar(), self.header, self.tabs.tabBar(), self.fav_bar, self.wf_toolbar):
                w.setVisible(True)
            self.audio_scroll.setVisible(getattr(self, "_pres_audio", True) and self.audio_action.isChecked())
            self.showMaximized() if getattr(self, "_pres_was_max", False) else self.showNormal()
        self.settings_panel.pres_btn.setText("Sair do modo apresentação" if on else "Entrar no modo apresentação")

    def _escape(self):
        if self._presenting:
            self.set_presentation(False)
            return
        self._stop_scan()
        self._sscan_stop()

    # ================================================================== reconectar ao abrir
    def _auto_reconnect(self):
        c = self.cfg
        if (not c.get("reconnect_on_start", True) or not c.get("rx_was_on")
                or c.get("source") not in ("RTL-SDR", "rtl_tcp", "SoapySDR") or self.engine.running):
            return
        rp = self.rx_panel
        if rp.source.currentText() != c["source"]:
            rp.source.setCurrentText(c["source"])
        if c["source"] == "RTL-SDR":
            real = [rp.device.itemText(i) for i in range(rp.device.count()) if rp.device.itemText(i)[:1].isdigit()]
            if not real:
                self._reconnect_failed("RTL-SDR não encontrado. Conecte o dongle e clique em Ligar.")
                return
            name = c.get("device_name", "").split(":", 1)[-1].strip()
            pick = next((t for t in real if name and t.split(":", 1)[-1].strip() == name), None)
            if pick is None:
                idx = int(c.get("device_index", 0))
                pick = next((t for t in real if t.split(":", 1)[0].strip() == str(idx)), real[0])
            rp.device.setCurrentText(pick)
        self._quiet_start, self._quiet_error = True, ""
        try:
            rp.start_btn.setChecked(True)
        finally:
            self._quiet_start = False
        if self.engine.running:
            self.statusBar().showMessage(f"Receptor reconectado ({c['source']}), como estava ao fechar", 8000)
        else:
            self._reconnect_failed(self._quiet_error or "não foi possível abrir o receptor.")

    def _reconnect_failed(self, why: str):
        msg = f"Reconexão automática do {self.cfg.get('source')}: {why}"
        log.warning(msg)
        self.rx_panel.info.setText(msg)
        self.hdr_summary.setText("Receptor parado — " + why.split("\n")[0][:120])
        self.statusBar().showMessage(msg.split("\n")[0], 15000)

    def apply_level(self, name: str):
        """Mostra/esconde recursos conforme o nível (as configurações nunca se perdem)."""
        if name not in LEVELS:
            name = "Avançado"
        lvl = LEVELS.index(name)
        self.cfg["ui_level"] = name
        for combo in (self.level_combo,):
            combo.blockSignals(True)
            combo.setCurrentText(name)
            combo.blockSignals(False)
        for act in getattr(self, "_level_actions", []):
            act.setChecked(act.text() == name)
        page_lvl = {"scan": 1, "adsb": 1, "ais": 1, "sondes": 1, "extras": 2, "sat": 1}
        for key, page in self.pages.items():
            vis = lvl >= page_lvl.get(key, 0)
            i = self.tabs.indexOf(page)
            self.tabs.setTabVisible(i, vis)
            self._tab_actions[i].setVisible(vis)
            if not vis and self.tabs.currentIndex() == i:
                self.tabs.setCurrentIndex(0)
        group_lvl = {"Sintonizador": 0, "AGC / Ruído": 2, "Equalizador": 1, "Saída / Gravação": 1,
                     "Voltar no tempo": 2, "Assistente de sintonia": 1}
        from PySide6.QtWidgets import QFormLayout, QGroupBox
        for panel in (self.rx_panel, self.mode_panel, self.audio_panel):
            for g in panel.findChildren(QGroupBox):
                need = group_lvl.get(g.title())
                if need is not None:
                    g.setVisible(lvl >= need)
        rp, mp = self.rx_panel, self.mode_panel
        for w in (rp.ppm, rp.bias, rp.direct, mp.cw_pitch, mp.deemph, mp.nfm_deemph):
            form = w.parentWidget().layout()
            if isinstance(form, QFormLayout):
                form.setRowVisible(w, lvl >= 2)
        for a, need in getattr(self, "_tb_levels", []):
            a.setVisible(lvl >= need)

    def _show_shortcuts(self):
        QMessageBox.information(self, "Atalhos", (
            "<b>Display LCD</b>: roda do mouse sobre um dígito altera o dígito; clique em cima/baixo do dígito;"
            " digite a frequência em MHz + Enter; setas ←/→ passo, ↑/↓ passo×10.<br>"
            "<b>Waterfall</b>: clique sintoniza; arraste o passband para sintonizar ou as bordas para largura;"
            " roda = zoom; Ctrl+roda = sintonia; duplo clique = zoom total.<br>"
            "<b>Teclado</b>: Alt+N/W/A/U/L/C modos; Ctrl+←/→ passo; Ctrl+↑/↓ passo×10; Ctrl+M salvar memória;"
            " Ctrl+B trocar VFO; Ctrl+S squelch automático; Ctrl+L níveis automáticos; Ctrl+Shift+M mudo;"
            " Ctrl+1…6 abas; F11 modo apresentação; Esc sai da apresentação ou para a varredura."))

    def closeEvent(self, ev):
        self._stop_sonde()
        self.rigctl_panel.stop()
        if self.web is not None:
            self.web.stop()
        if self.transcriber is not None:
            self.transcriber.stop()
        if self.caption_worker is not None:
            self.caption_worker.stop()
            self.caption_worker = None
        presenting = self._presenting
        if presenting:  # a geometria salva é a da janela normal
            self.set_presentation(False)
        self.cfg["presentation"] = presenting
        self._remember_current_band()
        s = QSettings("PT2VHF", "SDRTool")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("split_v05", self.main_split.saveState())
        s.setValue("audio_panel", "true" if self.audio_action.isChecked() else "false")
        self.cfg["rx_was_on"] = bool(self.engine.running and self.cfg.get("source") in ("RTL-SDR", "rtl_tcp", "SoapySDR"))
        self.cfg["vfo_freq"] = self.vfos["A"]["freq"] if self.active_vfo != "A" else self.engine.vfo
        self.cfg["fft_size"] = self.engine.fft_size
        self.cfg["my_locator"] = self.dec_panel.locator.text()
        self.cfg.save()
        self.bank.save()
        self.occupancy.flush(force=True)
        self.engine.stop()
        self.audio.stop()
        super().closeEvent(ev)


def _scroll(w):
    from PySide6.QtWidgets import QFrame, QScrollArea
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # o conteúdo se ajusta à largura
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(w)
    return sa
