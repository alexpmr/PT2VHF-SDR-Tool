"""Painéis de controle (abas) da janela principal."""
from __future__ import annotations

import csv
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QSlider, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ..audio import list_output_devices
from ..decoders.aprs import distance_bearing, locator_to_latlon
from ..decoders.tones import CTCSS_TONES
from ..dsp.audiofx import EQ_BANDS_HZ, EQ_PRESETS
from ..dsp.receiver import MODES, SAMPLE_RATES
from ..memory import BAND_PLAN, MemoryBank, MemoryChannel
from ..sources.network_sources import soapy_devices
from ..sources.rtlsdr_source import list_devices

STEPS = [10, 50, 100, 500, 1000, 2500, 5000, 6250, 8330, 9000, 10000, 12500, 25000, 50000, 100000]
SOURCES = ["Simulador", "RTL-SDR", "rtl_tcp", "SoapySDR", "Arquivo IQ"]


def fmt_freq(hz: float) -> str:
    return f"{hz / 1e6:,.4f}".replace(",", " ")


def fmt_step(hz: int) -> str:
    return f"{hz / 1000:g} kHz" if hz >= 1000 else f"{hz} Hz"


def hslider(lo, hi, val):
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(int(val))
    return s


# =============================================================================
class ReceiverPanel(QWidget):
    startRequested = Signal(dict)
    stopRequested = Signal()
    gainChanged = Signal(object)        # float ou None (AGC)
    ppmChanged = Signal(int)
    biasTeeChanged = Signal(bool)
    directSamplingChanged = Signal(int)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.source = QComboBox()
        self.source.addItems(SOURCES)
        self.source.setCurrentText(cfg["source"])
        form.addRow("Fonte:", self.source)

        self.device = QComboBox()
        dev_row = QHBoxLayout()
        dev_row.addWidget(self.device, 1)
        self.refresh = QPushButton("↻")
        self.refresh.setFixedWidth(30)
        self.refresh.setToolTip("Procurar dispositivos")
        dev_row.addWidget(self.refresh)
        form.addRow("Dispositivo:", dev_row)

        self.host = QLineEdit(cfg["rtl_tcp_host"])
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(cfg["rtl_tcp_port"])
        net = QHBoxLayout()
        net.addWidget(self.host, 1)
        net.addWidget(self.port)
        self.net_label = QLabel("Servidor:")
        form.addRow(self.net_label, net)

        self.file_edit = QLineEdit()
        self.file_btn = QPushButton("…")
        self.file_btn.setFixedWidth(30)
        fr = QHBoxLayout()
        fr.addWidget(self.file_edit, 1)
        fr.addWidget(self.file_btn)
        self.file_label = QLabel("Arquivo:")
        form.addRow(self.file_label, fr)

        self.rate = QComboBox()
        for r in SAMPLE_RATES:
            self.rate.addItem(f"{r / 1e6:g} MS/s", r)
        idx = self.rate.findData(cfg["sample_rate"])
        self.rate.setCurrentIndex(idx if idx >= 0 else 2)
        form.addRow("Amostragem:", self.rate)
        lay.addLayout(form)

        self.start_btn = QPushButton("▶  Ligar")
        self.start_btn.setCheckable(True)
        self.start_btn.setMinimumHeight(34)
        self.start_btn.setObjectName("powerButton")
        lay.addWidget(self.start_btn)

        g = QGroupBox("Sintonizador")
        gf = QFormLayout(g)
        self.tuner_agc = QCheckBox("AGC do sintonizador")
        self.tuner_agc.setChecked(cfg["gain"] is None)
        gf.addRow(self.tuner_agc)
        self.gain = hslider(0, 500, (cfg["gain"] or 30) * 10)
        self.gain_label = QLabel()
        gr = QHBoxLayout()
        gr.addWidget(self.gain, 1)
        gr.addWidget(self.gain_label)
        gf.addRow("Ganho RF:", gr)
        self.ppm = QSpinBox()
        self.ppm.setRange(-200, 200)
        self.ppm.setValue(cfg["ppm"])
        self.ppm.setSuffix(" ppm")
        gf.addRow("Correção:", self.ppm)
        self.bias = QCheckBox("Bias-T (alimenta LNA)")
        self.bias.setChecked(cfg["bias_tee"])
        gf.addRow(self.bias)
        self.direct = QComboBox()
        self.direct.addItems(["Desligada", "Ramo I", "Ramo Q (HF RTL-SDR V3)"])
        self.direct.setCurrentIndex(cfg["direct_sampling"])
        gf.addRow("Amostr. direta:", self.direct)
        lay.addWidget(g)

        self.info = QLabel("Parado")
        self.info.setWordWrap(True)
        self.info.setObjectName("infoLabel")
        lay.addWidget(self.info)
        lay.addStretch(1)

        self.source.currentTextChanged.connect(self._source_changed)
        self.refresh.clicked.connect(self.refresh_devices)
        self.file_btn.clicked.connect(self._browse)
        self.start_btn.toggled.connect(self._toggle)
        self.gain.valueChanged.connect(self._gain)
        self.tuner_agc.toggled.connect(self._gain)
        self.ppm.valueChanged.connect(self.ppmChanged)
        self.bias.toggled.connect(self.biasTeeChanged)
        self.direct.currentIndexChanged.connect(self.directSamplingChanged)
        self._source_changed(self.source.currentText())
        self._update_gain_label()

    def _source_changed(self, name):
        net = name == "rtl_tcp"
        self.host.setVisible(net)
        self.port.setVisible(net)
        self.net_label.setVisible(net)
        fil = name == "Arquivo IQ"
        self.file_edit.setVisible(fil)
        self.file_btn.setVisible(fil)
        self.file_label.setVisible(fil)
        self.rate.setEnabled(not fil)
        self.refresh_devices()

    def refresh_devices(self):
        self.device.clear()
        name = self.source.currentText()
        if name == "RTL-SDR":
            devs = list_devices()
            self.device.addItems(devs or ["(nenhum RTL-SDR encontrado)"])
        elif name == "SoapySDR":
            devs = soapy_devices()
            self.device.setEditable(True)
            self.device.addItems(devs or [self.cfg.get("soapy_args", "")])
        else:
            self.device.addItem({"Simulador": "Banda de 2 m sintética",
                                 "rtl_tcp": "Servidor remoto",
                                 "Arquivo IQ": "WAV estéreo I/Q"}[name])
        self.device.setEnabled(name in ("RTL-SDR", "SoapySDR"))

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Abrir gravação IQ", "", "WAV IQ (*.wav)")
        if p:
            self.file_edit.setText(p)

    def _toggle(self, on):
        if on:
            dev = self.device.currentText()
            self.startRequested.emit({
                "source": self.source.currentText(),
                "device_index": int(dev.split(":")[0]) if dev[:1].isdigit() else 0,
                "soapy_args": dev if self.source.currentText() == "SoapySDR" else "",
                "host": self.host.text(), "port": self.port.value(),
                "file": self.file_edit.text(), "sample_rate": self.rate.currentData(),
                "gain": self.current_gain(), "ppm": self.ppm.value(),
            })
        else:
            self.stopRequested.emit()

    def set_running(self, running: bool):
        self.start_btn.blockSignals(True)
        self.start_btn.setChecked(running)
        self.start_btn.setText("■  Desligar" if running else "▶  Ligar")
        self.start_btn.blockSignals(False)
        for w in (self.source, self.device, self.rate, self.host, self.port, self.file_edit):
            w.setEnabled(not running)

    def current_gain(self):
        return None if self.tuner_agc.isChecked() else self.gain.value() / 10

    def _update_gain_label(self):
        self.gain_label.setText("AGC" if self.tuner_agc.isChecked() else f"{self.gain.value() / 10:.1f} dB")
        self.gain.setEnabled(not self.tuner_agc.isChecked())

    def _gain(self, *_):
        self._update_gain_label()
        self.gainChanged.emit(self.current_gain())


# =============================================================================
class ModePanel(QWidget):
    modeChanged = Signal(str)
    bandwidthChanged = Signal(float)
    stepChanged = Signal(int)
    bandSelected = Signal(object)
    vfoAction = Signal(str)  # "A", "B", "swap", "copy"
    cwPitchChanged = Signal(float)
    deemphChanged = Signal(int)
    nfmDeemphChanged = Signal(bool)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        vg = QGroupBox("VFO")
        vl = QHBoxLayout(vg)
        self.vfo_btns = {}
        for name, act in (("A", "A"), ("B", "B"), ("A⇄B", "swap"), ("A=B", "copy")):
            b = QPushButton(name)
            b.setCheckable(act in ("A", "B"))
            b.clicked.connect(lambda _=False, a=act: self.vfoAction.emit(a))
            vl.addWidget(b)
            self.vfo_btns[act] = b
        self.vfo_btns["A"].setChecked(True)
        lay.addWidget(vg)

        # os modos ficam no display (teclas clicáveis) e nos atalhos Alt+N/W/A/U/L/C/O
        self.mode_btns = {}
        mode_hint = QLabel("Modo: use as teclas do display (AUTO, NFM, WFM, AM, USB, LSB, CW, DSB, RAW) "
                           "ou Alt+N/W/A/U/L/C, Alt+O = AUTO.")
        mode_hint.setWordWrap(True)
        mode_hint.setObjectName("hintLabel")
        lay.addWidget(mode_hint)

        fg = QGroupBox("Filtro / passo")
        fl = QFormLayout(fg)
        self.bw_presets = QHBoxLayout()
        self.bw_preset_w = QWidget()
        self.bw_preset_w.setLayout(self.bw_presets)
        self.bw_presets.setContentsMargins(0, 0, 0, 0)
        fl.addRow(self.bw_preset_w)
        self.bw = QDoubleSpinBox()
        self.bw.setRange(0.05, 200)
        self.bw.setDecimals(2)
        self.bw.setSuffix(" kHz")
        self.bw.setKeyboardTracking(False)
        fl.addRow("Largura:", self.bw)
        self.step = QComboBox()
        for s in STEPS:
            self.step.addItem(fmt_step(s), s)
        fl.addRow("Passo:", self.step)
        self.cw_pitch = QSpinBox()
        self.cw_pitch.setRange(300, 1200)
        self.cw_pitch.setValue(700)
        self.cw_pitch.setSuffix(" Hz")
        fl.addRow("Tom CW:", self.cw_pitch)
        self.deemph = QComboBox()
        self.deemph.addItem("75 µs (Américas)", 75)
        self.deemph.addItem("50 µs (Europa)", 50)
        self.deemph.setCurrentIndex(0 if cfg["wfm_deemph_us"] == 75 else 1)
        fl.addRow("De-ênfase WFM:", self.deemph)
        self.nfm_deemph = QCheckBox("De-ênfase em NFM")
        fl.addRow(self.nfm_deemph)
        lay.addWidget(fg)

        bg = QGroupBox("Bandas")
        bl = QVBoxLayout(bg)
        self.band = QComboBox()
        self.band.addItem("— escolher banda —", None)
        for b in BAND_PLAN:
            self.band.addItem(f"{b.name}  ({b.start / 1e6:g}–{b.end / 1e6:g} MHz)", b)
        bl.addWidget(self.band)
        lay.addWidget(bg)
        lay.addStretch(1)

        self.bw.valueChanged.connect(lambda v: self.bandwidthChanged.emit(v * 1000))
        self.step.currentIndexChanged.connect(lambda _i: self.stepChanged.emit(self.step.currentData()))
        self.band.activated.connect(self._band)
        self.cw_pitch.valueChanged.connect(lambda v: self.cwPitchChanged.emit(float(v)))
        self.deemph.currentIndexChanged.connect(lambda _i: self.deemphChanged.emit(self.deemph.currentData()))
        self.nfm_deemph.toggled.connect(self.nfmDeemphChanged)

    def _band(self, idx):
        b = self.band.itemData(idx)
        if b is not None:
            self.bandSelected.emit(b)
        self.band.setCurrentIndex(0)

    def show_mode(self, mode: str, bw: float, step: int):
        b = self.mode_btns.get(mode)
        if b:
            b.setChecked(True)
        self.bw.blockSignals(True)
        self.bw.setValue(bw / 1000)
        self.bw.blockSignals(False)
        self.step.blockSignals(True)
        i = self.step.findData(step)
        if i < 0:
            self.step.addItem(fmt_step(step), step)
            i = self.step.count() - 1
        self.step.setCurrentIndex(i)
        self.step.blockSignals(False)
        while self.bw_presets.count():
            w = self.bw_presets.takeAt(0).widget()
            if w:
                w.deleteLater()
        for p in MODES[mode].bw_presets:
            btn = QPushButton(f"{p / 1000:g}k")
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _=False, pp=p: self.bandwidthChanged.emit(float(pp)))
            self.bw_presets.addWidget(btn)

    def set_vfo(self, name: str):
        self.vfo_btns["A"].setChecked(name == "A")
        self.vfo_btns["B"].setChecked(name == "B")


# =============================================================================
def _compact(widget):
    """Formulários quebram em duas linhas quando o painel é estreito (rótulo em cima)."""
    from PySide6.QtWidgets import QSizePolicy
    for form in widget.findChildren(QFormLayout):
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    widgets = [w for cls in (QComboBox, QDoubleSpinBox, QSpinBox, QSlider) for w in widget.findChildren(cls)]
    for w in widgets:
        w.setMinimumWidth(40)
        if w.sizePolicy().horizontalPolicy() == QSizePolicy.Fixed:
            continue
        w.setSizePolicy(QSizePolicy.Ignored if isinstance(w, QComboBox) else QSizePolicy.Expanding,
                        w.sizePolicy().verticalPolicy())


class AudioPanel(QWidget):
    volumeChanged = Signal(float)
    muteChanged = Signal(bool)
    squelchChanged = Signal(float)
    squelchAuto = Signal()
    agcChanged = Signal(bool, str)
    manualGainChanged = Signal(float)
    nbChanged = Signal(bool, float)
    nrChanged = Signal(bool, float)
    notchChanged = Signal(bool, float)
    ctcssFilterChanged = Signal(bool)
    lowpassChanged = Signal(float)
    eqChanged = Signal(bool, list)
    recordAudio = Signal(bool)
    recordIQ = Signal(bool)
    deviceChanged = Signal(object)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)

        g = QGroupBox("Volume / Squelch")
        f = QFormLayout(g)
        self.volume = hslider(0, 100, cfg["volume"] * 100)
        self.mute = QCheckBox("Mudo")
        vr = QHBoxLayout()
        vr.addWidget(self.volume, 1)
        vr.addWidget(self.mute)
        f.addRow("Volume:", vr)
        self.squelch = hslider(-150, 0, cfg["squelch"])
        self.sq_label = QLabel()
        self.sq_auto = QPushButton("Auto")
        self.sq_auto.setToolTip("Ajusta o squelch 6 dB acima do ruído atual")
        sr = QHBoxLayout()
        sr.addWidget(self.squelch, 1)
        sr.addWidget(self.sq_label)
        sr.addWidget(self.sq_auto)
        f.addRow("Squelch:", sr)
        lay.addWidget(g)

        g = QGroupBox("AGC / Ruído")
        f = QFormLayout(g)
        self.agc = QCheckBox("AGC")
        self.agc.setChecked(cfg["agc"])
        self.agc_speed = QComboBox()
        self.agc_speed.addItems(["Rápido", "Médio", "Lento"])
        self.agc_speed.setCurrentText(cfg["agc_speed"])
        ar = QHBoxLayout()
        ar.addWidget(self.agc)
        ar.addWidget(self.agc_speed, 1)
        f.addRow(ar)
        self.man_gain = hslider(-20, 60, 20)
        f.addRow("Ganho AF manual:", self.man_gain)
        self.nb = QCheckBox("NB")
        self.nb_thr = QDoubleSpinBox()
        self.nb_thr.setRange(2, 20)
        self.nb_thr.setValue(6)
        self.nb_thr.setPrefix("limiar ")
        nbr = QHBoxLayout()
        nbr.addWidget(self.nb)
        nbr.addWidget(self.nb_thr, 1)
        f.addRow("Noise blanker:", nbr)
        self.nr = QCheckBox("NR")
        self.nr_str = hslider(5, 40, 15)
        nrr = QHBoxLayout()
        nrr.addWidget(self.nr)
        nrr.addWidget(self.nr_str, 1)
        f.addRow("Redução ruído:", nrr)
        self.notch = QCheckBox("Notch")
        self.notch_f = QSpinBox()
        self.notch_f.setRange(50, 5000)
        self.notch_f.setValue(1000)
        self.notch_f.setSuffix(" Hz")
        ntr = QHBoxLayout()
        ntr.addWidget(self.notch)
        ntr.addWidget(self.notch_f, 1)
        f.addRow("Notch manual:", ntr)
        self.ctcss_hp = QCheckBox("Filtrar sub-tom (< 300 Hz)")
        f.addRow(self.ctcss_hp)
        self.lowpass = QComboBox()
        for name, hz in (("Sem filtro", 0), ("2,4 kHz", 2400), ("3 kHz", 3000), ("4 kHz", 4000),
                         ("5 kHz", 5000), ("8 kHz", 8000)):
            self.lowpass.addItem(name, hz)
        f.addRow("Passa-baixas AF:", self.lowpass)
        lay.addWidget(g)

        g = QGroupBox("Equalizador")
        el = QVBoxLayout(g)
        top = QHBoxLayout()
        self.eq_on = QCheckBox("Ativo")
        self.eq_on.setChecked(cfg["eq_enabled"])
        self.eq_preset = QComboBox()
        self.eq_preset.addItems(list(EQ_PRESETS))
        top.addWidget(self.eq_on)
        top.addWidget(self.eq_preset, 1)
        el.addLayout(top)
        sl = QHBoxLayout()
        self.eq_sliders = []
        for i, fz in enumerate(EQ_BANDS_HZ):
            col = QVBoxLayout()
            s = QSlider(Qt.Vertical)
            s.setRange(-15, 15)
            s.setValue(int(cfg["eq_gains"][i]) if i < len(cfg["eq_gains"]) else 0)
            s.setMinimumHeight(90)
            s.setTickPosition(QSlider.TicksBothSides)
            s.setTickInterval(5)
            lab = QLabel(f"{fz / 1000:g}k" if fz >= 1000 else str(fz))
            lab.setAlignment(Qt.AlignCenter)
            col.addWidget(s, 1, Qt.AlignHCenter)
            col.addWidget(lab)
            sl.addLayout(col)
            self.eq_sliders.append(s)
            s.valueChanged.connect(self._eq)
        el.addLayout(sl)
        lay.addWidget(g)

        g = QGroupBox("Saída / Gravação")
        f = QFormLayout(g)
        self.device = QComboBox()
        self.device.addItem("Padrão do sistema", None)
        for i, name in list_output_devices():
            self.device.addItem(name, i)
        f.addRow("Placa de som:", self.device)
        self.rec_audio = QPushButton("● Gravar áudio")
        self.rec_audio.setCheckable(True)
        self.rec_iq = QPushButton("● Gravar IQ")
        self.rec_iq.setCheckable(True)
        rr = QHBoxLayout()
        rr.addWidget(self.rec_audio)
        rr.addWidget(self.rec_iq)
        f.addRow(rr)
        self.vox = QCheckBox("VOX: gravar só quando houver transmissão")
        self.vox.setToolTip("Grava apenas enquanto o squelch estiver aberto (com 0,5 s antes, para não cortar a fala)")
        f.addRow(self.vox)
        self.vox_files = QComboBox()
        self.vox_files.addItem("Arquivo único (sem os silêncios)", True)
        self.vox_files.addItem("Um arquivo por transmissão", False)
        f.addRow("Arquivos VOX:", self.vox_files)
        lay.addWidget(g)
        lay.addStretch(1)

        self.volume.valueChanged.connect(lambda v: self.volumeChanged.emit(v / 100))
        self.mute.toggled.connect(self.muteChanged)
        self.squelch.valueChanged.connect(self._sq)
        self.sq_auto.clicked.connect(self.squelchAuto)
        self.agc.toggled.connect(lambda _: self.agcChanged.emit(self.agc.isChecked(), self.agc_speed.currentText()))
        self.agc_speed.currentTextChanged.connect(lambda _: self.agcChanged.emit(self.agc.isChecked(), self.agc_speed.currentText()))
        self.man_gain.valueChanged.connect(lambda v: self.manualGainChanged.emit(float(v)))
        self.nb.toggled.connect(lambda _: self.nbChanged.emit(self.nb.isChecked(), self.nb_thr.value()))
        self.nb_thr.valueChanged.connect(lambda _: self.nbChanged.emit(self.nb.isChecked(), self.nb_thr.value()))
        self.nr.toggled.connect(lambda _: self.nrChanged.emit(self.nr.isChecked(), self.nr_str.value() / 10))
        self.nr_str.valueChanged.connect(lambda _: self.nrChanged.emit(self.nr.isChecked(), self.nr_str.value() / 10))
        self.notch.toggled.connect(lambda _: self.notchChanged.emit(self.notch.isChecked(), float(self.notch_f.value())))
        self.notch_f.valueChanged.connect(lambda _: self.notchChanged.emit(self.notch.isChecked(), float(self.notch_f.value())))
        self.ctcss_hp.toggled.connect(self.ctcssFilterChanged)
        self.lowpass.currentIndexChanged.connect(lambda _: self.lowpassChanged.emit(float(self.lowpass.currentData())))
        self.eq_on.toggled.connect(self._eq)
        self.eq_preset.currentTextChanged.connect(self._preset)
        self.rec_audio.toggled.connect(self.recordAudio)
        self.rec_iq.toggled.connect(self.recordIQ)
        self.device.currentIndexChanged.connect(lambda _: self.deviceChanged.emit(self.device.currentData()))
        self._sq(self.squelch.value(), emit=False)
        _compact(self)

    def _sq(self, v, emit=True):
        self.sq_label.setText("aberto" if v <= -150 else f"{v} dB")
        if emit:
            self.squelchChanged.emit(float(v))

    def set_squelch(self, v: float):
        self.squelch.setValue(int(v))

    def _preset(self, name):
        for s, g in zip(self.eq_sliders, EQ_PRESETS[name]):
            s.blockSignals(True)
            s.setValue(int(g))
            s.blockSignals(False)
        if name != "Plano":
            self.eq_on.setChecked(True)
        self._eq()

    def _eq(self, *_):
        self.eqChanged.emit(self.eq_on.isChecked(), [s.value() for s in self.eq_sliders])

    def eq_gains(self):
        return [s.value() for s in self.eq_sliders]


# =============================================================================
class MemoryDialog(QDialog):
    def __init__(self, bank: MemoryBank, ch: MemoryChannel, parent=None, title="Memória"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.ch = ch
        f = QFormLayout(self)
        self.name = QLineEdit(ch.name)
        self.freq = QDoubleSpinBox()
        self.freq.setRange(0.024, 1766.0)
        self.freq.setDecimals(6)
        self.freq.setSuffix(" MHz")
        self.freq.setValue(ch.freq / 1e6)
        self.mode = QComboBox()
        self.mode.addItems(list(MODES))
        self.mode.setCurrentText(ch.mode)
        self.bw = QDoubleSpinBox()
        self.bw.setRange(0.05, 200)
        self.bw.setSuffix(" kHz")
        self.bw.setValue(ch.bandwidth / 1000)
        self.cat = QComboBox()
        self.cat.setEditable(True)
        self.cat.addItems(bank.categories)
        self.cat.setCurrentText(ch.category)
        self.tone = QComboBox()
        self.tone.addItem("Nenhum", None)
        for t in CTCSS_TONES:
            self.tone.addItem(f"{t:.1f} Hz", t)
        if ch.ctcss:
            self.tone.setCurrentIndex(max(0, self.tone.findData(ch.ctcss)))
        self.offset = QDoubleSpinBox()
        self.offset.setRange(-100, 100)
        self.offset.setDecimals(3)
        self.offset.setSuffix(" MHz")
        self.offset.setValue(ch.offset / 1e6)
        self.notes = QLineEdit(ch.notes)
        self.fav = QCheckBox("Favorito")
        self.fav.setChecked(ch.favorite)
        self.skip = QCheckBox("Pular na varredura")
        self.skip.setChecked(ch.skip_scan)
        for label, w in (("Nome:", self.name), ("Frequência:", self.freq), ("Modo:", self.mode),
                         ("Largura:", self.bw), ("Categoria:", self.cat), ("CTCSS:", self.tone),
                         ("Desloc. repetidora:", self.offset), ("Notas:", self.notes)):
            f.addRow(label, w)
        f.addRow(self.fav)
        f.addRow(self.skip)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def result_channel(self) -> MemoryChannel:
        c = self.ch
        c.name = self.name.text() or f"{self.freq.value():.4f}"
        c.freq = self.freq.value() * 1e6
        c.mode = self.mode.currentText()
        c.bandwidth = self.bw.value() * 1000
        c.category = self.cat.currentText() or "Simplex"
        c.ctcss = self.tone.currentData()
        c.offset = self.offset.value() * 1e6
        c.notes = self.notes.text()
        c.favorite = self.fav.isChecked()
        c.skip_scan = self.skip.isChecked()
        return c


class MemoryPanel(QWidget):
    recallRequested = Signal(object)
    saveCurrentRequested = Signal()
    scanRequested = Signal(str, object)  # "memory", categoria
    scanStop = Signal()
    changed = Signal()
    presetsRequested = Signal()

    def __init__(self, bank: MemoryBank, parent=None):
        super().__init__(parent)
        self.bank = bank
        lay = QVBoxLayout(self)
        tb = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por nome, frequência, notas…")
        tb.addWidget(self.search, 1)
        for text, slot, tip in (("Memórias prontas…", self.presetsRequested.emit,
                                 "Pacotes de frequências padronizadas (marítimo, PX, FRS, aviação, satélites…)"),
                                ("★ Favorito", self._toggle_fav, "Liga/desliga favorito (tecla de acesso rápido)"),
                                ("+ Atual", self.saveCurrentRequested.emit, "Salvar frequência atual (Ctrl+M)"),
                                ("Editar", self._edit, ""), ("Excluir", self._delete, ""),
                                ("Categoria +", self._new_cat, "Nova categoria"),
                                ("Importar CSV", self._import, "Importa CSV do CHIRP"),
                                ("Exportar CSV", self._export, "Exporta CSV compatível com CHIRP")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            tb.addWidget(b)
        lay.addLayout(tb)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nome", "Frequência (MHz)", "Modo", "Largura", "Banda", "CTCSS", "Notas"])
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(QHeaderView.Interactive)
        self.tree.setColumnWidth(0, 170)
        self.tree.setColumnWidth(1, 120)
        lay.addWidget(self.tree, 1)

        sc = QHBoxLayout()
        self.scan_mem = QPushButton("⟳ Varrer categoria")
        self.scan_mem.setToolTip("Varre os canais da categoria selecionada (ou favoritos)")
        self.scan_stop = QPushButton("■ Parar")
        self.dwell = QSpinBox()
        self.dwell.setRange(50, 3000)
        self.dwell.setValue(150)
        self.dwell.setSuffix(" ms")
        self.dwell.setToolTip("Tempo de permanência por canal")
        self.resume = QDoubleSpinBox()
        self.resume.setRange(0, 30)
        self.resume.setValue(3)
        self.resume.setSuffix(" s")
        self.resume.setToolTip("Retomar a varredura após o sinal cair (0 = parar no sinal)")
        hint = QLabel("Para varrer faixas inteiras e descobrir frequências, use o painel Scanner.")
        hint.setObjectName("infoLabel")
        for w in (self.scan_mem, QLabel("Perm.:"), self.dwell, QLabel("Retomar:"), self.resume,
                  self.scan_stop):
            sc.addWidget(w)
        sc.addStretch(1)
        sc.addWidget(hint)
        lay.addLayout(sc)

        self.tree.itemDoubleClicked.connect(self._recall)
        self.search.textChanged.connect(self.refresh)
        self.scan_mem.clicked.connect(self._scan_memory)
        self.scan_stop.clicked.connect(self.scanStop)
        self.refresh()

    def refresh(self):
        flt = self.search.text().lower().strip()
        expanded = {self.tree.topLevelItem(i).text(0) for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        self.tree.clear()
        cats = list(self.bank.categories)
        for c in self.bank.channels:
            if c.category not in cats:
                cats.append(c.category)
        for cat in cats:
            chans = self.bank.by_category(cat)
            if flt:
                chans = [c for c in chans if flt in c.name.lower() or flt in f"{c.freq / 1e6:.4f}"
                         or flt in c.notes.lower() or flt in c.band.lower()]
                if not chans:
                    continue
            top = QTreeWidgetItem([cat, f"{len(chans)} canais"])
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setData(0, Qt.UserRole, ("cat", cat))
            self.tree.addTopLevelItem(top)
            for c in chans:
                it = QTreeWidgetItem([("★ " if c.favorite else "") + c.name, f"{c.freq / 1e6:.5f}", c.mode,
                                      f"{c.bandwidth / 1000:g}k", c.band,
                                      f"{c.ctcss:.1f}" if c.ctcss else "", c.notes])
                it.setData(0, Qt.UserRole, ("ch", c.id))
                top.addChild(it)
            top.setExpanded(bool(flt) or cat in expanded or not expanded)

    def _selected(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def _recall(self, item, _col):
        d = item.data(0, Qt.UserRole)
        if d and d[0] == "ch":
            ch = self.bank.get(d[1])
            if ch:
                self.recallRequested.emit(ch)

    def add_channel_dialog(self, ch: MemoryChannel):
        dlg = MemoryDialog(self.bank, ch, self, "Salvar memória")
        if dlg.exec():
            self.bank.add(dlg.result_channel())
            self._commit()

    def _edit(self):
        d = self._selected()
        if not d or d[0] != "ch":
            return
        ch = self.bank.get(d[1])
        dlg = MemoryDialog(self.bank, ch, self, "Editar memória")
        if dlg.exec():
            dlg.result_channel()
            if ch.category not in self.bank.categories:
                self.bank.categories.append(ch.category)
            self._commit()

    def _delete(self):
        d = self._selected()
        if not d:
            return
        if d[0] == "ch":
            self.bank.remove(d[1])
        elif QMessageBox.question(self, "Excluir categoria",
                                  f"Excluir a categoria '{d[1]}' e todos os seus canais?") == QMessageBox.Yes:
            self.bank.channels = [c for c in self.bank.channels if c.category != d[1]]
            if d[1] in self.bank.categories:
                self.bank.categories.remove(d[1])
        self._commit()

    def _new_cat(self):
        name, ok = QInputDialog.getText(self, "Nova categoria", "Nome:")
        if ok and name and name not in self.bank.categories:
            self.bank.categories.append(name)
            self._commit()

    def _import(self):
        p, _ = QFileDialog.getOpenFileName(self, "Importar CSV (CHIRP)", "", "CSV (*.csv)")
        if not p:
            return
        try:
            n = self.bank.import_csv(p)
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            QMessageBox.warning(self, "Importar", f"Erro: {e}")
            return
        QMessageBox.information(self, "Importar", f"{n} canais importados.")
        self._commit()

    def _export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Exportar CSV", "memorias_pt2vhf.csv", "CSV (*.csv)")
        if p:
            self.bank.export_csv(p)

    def _toggle_fav(self):
        d = self._selected()
        if not d or d[0] != "ch":
            return
        ch = self.bank.get(d[1])
        ch.favorite = not ch.favorite
        self._commit()

    def _scan_memory(self):
        d = self._selected()
        if d is None:
            cat = None
        elif d[0] == "cat":
            cat = d[1]
        else:
            ch = self.bank.get(d[1])
            cat = ch.category if ch else None
        self.scanRequested.emit("memory", cat)

    def _commit(self):
        self.bank.save()
        self.refresh()
        self.changed.emit()


# =============================================================================
class DecoderPanel(QWidget):
    enabledChanged = Signal(dict)
    toneSquelchChanged = Signal(object)

    APRS_COLS = ["Hora", "Indicativo", "Tipo", "Posição", "Dist. (km)", "Az.", "Vel. (km/h)",
                 "Alt. (m)", "Comentário / Mensagem", "Caminho"]

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.chk = {}
        for key, label in (("aprs", "APRS / AX.25 (1200 bd)"), ("dtmf", "DTMF"), ("ctcss", "CTCSS")):
            c = QCheckBox(label)
            c.setChecked(cfg["decoders"].get(key, True))
            c.toggled.connect(self._enabled)
            top.addWidget(c)
            self.chk[key] = c
        top.addSpacing(20)
        top.addWidget(QLabel("Tom squelch:"))
        self.tsq = QComboBox()
        self.tsq.addItem("Desligado", None)
        for t in CTCSS_TONES:
            self.tsq.addItem(f"{t:.1f} Hz", t)
        self.tsq.currentIndexChanged.connect(lambda _: self.toneSquelchChanged.emit(self.tsq.currentData()))
        top.addWidget(self.tsq)
        top.addSpacing(20)
        top.addWidget(QLabel("Meu locator:"))
        self.locator = QLineEdit(cfg["my_locator"])
        self.locator.setMaximumWidth(80)
        top.addWidget(self.locator)
        top.addStretch(1)
        self.ctcss_label = QLabel("CTCSS: —")
        self.ctcss_label.setObjectName("bigLabel")
        top.addWidget(self.ctcss_label)
        lay.addLayout(top)

        self.tabs = QTabWidget()
        self.aprs = QTableWidget(0, len(self.APRS_COLS))
        self.aprs.setHorizontalHeaderLabels(self.APRS_COLS)
        self.aprs.horizontalHeader().setStretchLastSection(True)
        self.aprs.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.aprs.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.aprs.verticalHeader().setVisible(False)
        self.aprs.setColumnWidth(8, 300)
        self.tabs.addTab(self.aprs, "APRS")

        self.stations = QTableWidget(0, 6)
        self.stations.setHorizontalHeaderLabels(["Indicativo", "Último", "Pacotes", "Posição", "Dist. (km)", "Último comentário"])
        self.stations.horizontalHeader().setStretchLastSection(True)
        self.stations.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stations.verticalHeader().setVisible(False)
        self.tabs.addTab(self.stations, "Estações")
        self._stations: dict[str, dict] = {}

        self.tlm = QTableWidget(0, 9)
        self.tlm.setHorizontalHeaderLabels(["Hora", "Estação", "Seq", "A1", "A2", "A3", "A4", "A5", "Bits"])
        self.tlm.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tlm.verticalHeader().setVisible(False)
        self.tabs.addTab(self.tlm, "Telemetria / Clima")

        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setMaximumBlockCount(5000)
        self.tabs.addTab(self.raw, "Pacotes brutos")

        dw = QWidget()
        dl = QVBoxLayout(dw)
        self.dtmf_line = QLineEdit()
        self.dtmf_line.setReadOnly(True)
        self.dtmf_line.setObjectName("dtmfLine")
        dl.addWidget(self.dtmf_line)
        self.dtmf_log = QPlainTextEdit()
        self.dtmf_log.setReadOnly(True)
        dl.addWidget(self.dtmf_log)
        self.tabs.addTab(dw, "DTMF")
        lay.addWidget(self.tabs, 1)

        br = QHBoxLayout()
        clear = QPushButton("Limpar")
        clear.clicked.connect(self.clear)
        save = QPushButton("Salvar log APRS…")
        save.clicked.connect(self._save)
        br.addStretch(1)
        br.addWidget(save)
        br.addWidget(clear)
        lay.addLayout(br)
        self._dtmf_last = 0.0
        self.counts = {"aprs": 0, "dtmf": 0}

    def _enabled(self, *_):
        self.enabledChanged.emit({k: c.isChecked() for k, c in self.chk.items()})

    def clear(self):
        for t in (self.aprs, self.tlm, self.stations):
            t.setRowCount(0)
        self._stations.clear()
        self.raw.clear()
        self.dtmf_line.clear()
        self.dtmf_log.clear()

    def _save(self):
        p, _ = QFileDialog.getSaveFileName(self, "Salvar log APRS", "aprs_log.csv", "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.APRS_COLS)
            for r in range(self.aprs.rowCount()):
                w.writerow([self.aprs.item(r, c).text() if self.aprs.item(r, c) else ""
                            for c in range(self.aprs.columnCount())])

    def _my_pos(self):
        return locator_to_latlon(self.locator.text())

    @staticmethod
    def _row(table: QTableWidget, values, top=True, limit=2000):
        r = 0 if top else table.rowCount()
        table.insertRow(r)
        for c, v in enumerate(values):
            table.setItem(r, c, QTableWidgetItem(str(v)))
        if table.rowCount() > limit:
            table.removeRow(table.rowCount() - 1)

    def add_aprs(self, pkt, ts: float):
        self.counts["aprs"] += 1
        hora = time.strftime("%H:%M:%S", time.localtime(ts))
        dist = az = ""
        me = self._my_pos()
        if me and pkt.lat is not None:
            d, b = distance_bearing(me[0], me[1], pkt.lat, pkt.lon)
            dist, az = f"{d:.1f}", f"{b:.0f}°"
        text = pkt.comment
        if pkt.type == "Mensagem":
            text = f"→ {pkt.message_to}: {pkt.message}"
        elif pkt.weather:
            wx = pkt.weather
            parts = []
            if "temp_C" in wx:
                parts.append(f"{wx['temp_C']} °C")
            if "umidade" in wx:
                parts.append(f"UR {wx['umidade']}%")
            if "pressao_dPa" in wx:
                parts.append(f"{wx['pressao_dPa'] / 10:.1f} hPa")
            if "dir_vento" in wx:
                parts.append(f"vento {wx['dir_vento']}° {wx.get('vel_vento_mph', 0) * 1.609:.0f} km/h")
            text = " | ".join(parts) + "  " + pkt.comment
        self._row(self.aprs, [hora, pkt.source, pkt.type, pkt.position_str(), dist, az,
                              f"{pkt.speed_kmh:.0f}" if pkt.speed_kmh is not None else "",
                              f"{pkt.altitude_m:.0f}" if pkt.altitude_m is not None else "",
                              text, pkt.path])
        self.raw.appendPlainText(f"[{hora}] {pkt.raw}")
        if pkt.telemetry:
            t = pkt.telemetry
            self._row(self.tlm, [hora, pkt.source, t.get("seq", ""), *[t.get(f"A{i}", "") for i in range(1, 6)],
                                 t.get("bits", "")])
        elif pkt.weather:
            wx = pkt.weather
            self._row(self.tlm, [hora, pkt.source, "WX", wx.get("temp_C", ""), wx.get("umidade", ""),
                                 wx.get("pressao_dPa", ""), wx.get("dir_vento", ""),
                                 wx.get("vel_vento_mph", ""), ""])
        st = self._stations.setdefault(pkt.source, {"n": 0, "pos": "", "dist": "", "comment": ""})
        st["n"] += 1
        st["last"] = hora
        if pkt.lat is not None:
            st["pos"], st["dist"] = pkt.position_str(), dist
        if text:
            st["comment"] = text
        self.stations.setRowCount(0)
        for call, s in sorted(self._stations.items(), key=lambda kv: kv[1]["last"], reverse=True):
            self._row(self.stations, [call, s["last"], s["n"], s["pos"], s["dist"], s["comment"]], top=False)

    def add_dtmf(self, digit: str, ts: float):
        self.counts["dtmf"] += 1
        if ts - self._dtmf_last > 3.0 and self.dtmf_line.text():
            self.dtmf_log.appendPlainText(f"[{time.strftime('%H:%M:%S', time.localtime(self._dtmf_last))}] "
                                          f"{self.dtmf_line.text()}")
            self.dtmf_line.clear()
        self.dtmf_line.setText(self.dtmf_line.text() + digit)
        self._dtmf_last = ts

    def set_ctcss(self, tone):
        self.ctcss_label.setText(f"CTCSS: {tone:.1f} Hz" if tone else "CTCSS: —")
