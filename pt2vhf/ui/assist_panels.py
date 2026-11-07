"""Interface dos recursos da v0.3: assistente de sintonia, voltar no tempo, receptores extras
e atualização pelo site oficial."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QProgressDialog, QPushButton,
                               QSlider, QVBoxLayout, QWidget)

from .. import __version__, updater
from ..dsp.receiver import MODES


class AssistBox(QGroupBox):
    """Assistente de sintonia (age no VFO e no filtro, não no áudio)."""

    autotuneRequested = Signal()
    detectRequested = Signal()
    filterRequested = Signal()

    def __init__(self, parent=None):
        super().__init__("Assistente de sintonia", parent)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.b_tune = QPushButton("Auto-sintonia SSB")
        self.b_tune.setToolTip("Analisa ~4 s de fonia e corrige o VFO pelos harmônicos da voz (USB/LSB)")
        self.b_mode = QPushButton("Detectar modo")
        self.b_mode.setToolTip("Identifica WFM, NFM, AM, USB/LSB ou CW e ajusta modo, filtro e sintonia")
        self.b_filter = QPushButton("Ajustar filtro")
        self.b_filter.setToolTip("Ajusta as bordas do passband à largura real do sinal")
        for b in (self.b_tune, self.b_mode, self.b_filter):
            row.addWidget(b)
        lay.addLayout(row)
        self.cont = QCheckBox("Auto-sintonia contínua em SSB (a cada 10 s com voz)")
        lay.addWidget(self.cont)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.result.setObjectName("infoLabel")
        lay.addWidget(self.result)
        self.b_tune.clicked.connect(self.autotuneRequested)
        self.b_mode.clicked.connect(self.detectRequested)
        self.b_filter.clicked.connect(self.filterRequested)

    def busy(self, text: str):
        for b in (self.b_tune, self.b_mode, self.b_filter):
            b.setEnabled(False)
        self.result.setText(text)

    def done(self, text: str):
        for b in (self.b_tune, self.b_mode, self.b_filter):
            b.setEnabled(True)
        self.result.setText(text)


class TimeShiftBox(QGroupBox):
    """Voltar no tempo: reouvir os últimos segundos de qualquer frequência da faixa."""

    bufferChanged = Signal(float)
    replayRequested = Signal(float)
    liveRequested = Signal()

    def __init__(self, seconds: float, parent=None):
        super().__init__("Voltar no tempo", parent)
        lay = QGridLayout(self)
        self.size = QComboBox()
        for label, v in (("Desligado", 0), ("10 s", 10), ("20 s", 20), ("30 s", 30), ("60 s", 60)):
            self.size.addItem(label, v)
        i = self.size.findData(int(seconds))
        self.size.setCurrentIndex(i if i >= 0 else 2)
        self.size.setToolTip("Memória usada: ~2 bytes por amostra (ex.: 20 s a 1,2 MS/s ≈ 48 MB)")
        lay.addWidget(QLabel("Buffer:"), 0, 0)
        lay.addWidget(self.size, 0, 1, 1, 3)
        self.b10 = QPushButton("⏪ 10 s")
        self.b30 = QPushButton("⏪ 30 s")
        self.blive = QPushButton("● Ao vivo")
        lay.addWidget(self.b10, 1, 0)
        lay.addWidget(self.b30, 1, 1)
        lay.addWidget(self.blive, 1, 2, 1, 2)
        self.status = QLabel("Ao vivo")
        self.status.setObjectName("infoLabel")
        lay.addWidget(self.status, 2, 0, 1, 4)
        self.size.currentIndexChanged.connect(lambda _: self.bufferChanged.emit(float(self.size.currentData())))
        self.b10.clicked.connect(lambda: self.replayRequested.emit(10.0))
        self.b30.clicked.connect(lambda: self.replayRequested.emit(30.0))
        self.blive.clicked.connect(self.liveRequested)


class ExtrasPanel(QWidget):
    """Até 4 receptores extras ouvidos junto com o principal (mesma faixa)."""

    addRequested = Signal()
    changed = Signal(object)          # ExtraReceiver alterado
    removeRequested = Signal(object)
    tuneMainRequested = Signal(float, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.add = QPushButton("+ Adicionar receptor na frequência atual")
        self.add.clicked.connect(self.addRequested)
        top.addWidget(self.add)
        hint = QLabel("Ouça até 4 canais da mesma faixa ao mesmo tempo (ex.: torre e solo do aeroporto).")
        hint.setObjectName("hintLabel")
        top.addWidget(hint, 1)
        self.lay.addLayout(top)
        self.grid = QGridLayout()
        for c, h in enumerate(["Ativo", "Frequência", "Modo", "Volume", "Squelch", "Nível", ""]):
            lab = QLabel(f"<b>{h}</b>")
            self.grid.addWidget(lab, 0, c)
        self.grid.setColumnStretch(7, 1)
        self.lay.addLayout(self.grid)
        self.lay.addStretch(1)
        self.rows: list[dict] = []

    def add_row(self, ex):
        r = len(self.rows) + 1
        on = QCheckBox()
        on.setChecked(ex.enabled)
        f = QDoubleSpinBox()
        f.setRange(0.024, 1766)
        f.setDecimals(5)
        f.setSuffix(" MHz")
        f.setValue(ex.freq / 1e6)
        f.setKeyboardTracking(False)
        mode = QComboBox()
        mode.addItems([m for m in MODES if m != "RAW"])
        mode.setCurrentText(ex.rx.mode)
        vol = QSlider(Qt.Horizontal)
        vol.setMaximumWidth(160)
        vol.setRange(0, 100)
        vol.setValue(int(ex.rx.volume * 100))
        sq = QSlider(Qt.Horizontal)
        sq.setMaximumWidth(160)
        sq.setRange(-150, 0)
        sq.setValue(int(ex.rx.squelch.threshold_db))
        level = QLabel("—")
        level.setMinimumWidth(90)
        btns = QHBoxLayout()
        go = QPushButton("Ouvir no principal")
        rm = QPushButton("✕")
        rm.setFixedWidth(28)
        btns.addWidget(go)
        btns.addWidget(rm)
        bw = QWidget()
        bw.setLayout(btns)
        for c, w in enumerate((on, f, mode, vol, sq, level, bw)):
            self.grid.addWidget(w, r, c)
        row = {"ex": ex, "widgets": (on, f, mode, vol, sq, level, bw), "level": level}
        self.rows.append(row)

        def upd(*_):
            ex.enabled = on.isChecked()
            ex.freq = f.value() * 1e6
            if mode.currentText() != ex.rx.mode:
                ex.rx.set_mode(mode.currentText())
            ex.rx.volume = vol.value() / 100
            ex.rx.squelch.threshold_db = float(sq.value())
            self.changed.emit(ex)
        for w, sig in ((on, on.toggled), (f, f.valueChanged), (mode, mode.currentTextChanged),
                       (vol, vol.valueChanged), (sq, sq.valueChanged)):
            sig.connect(upd)
        go.clicked.connect(lambda: self.tuneMainRequested.emit(ex.freq, ex.rx.mode))
        rm.clicked.connect(lambda: self.removeRequested.emit(ex))
        self.add.setEnabled(len(self.rows) < 4)

    def remove_row(self, ex):
        for row in list(self.rows):
            if row["ex"] is ex:
                for w in row["widgets"]:
                    self.grid.removeWidget(w)
                    w.deleteLater()
                self.rows.remove(row)
        # reorganiza as linhas restantes
        for i, row in enumerate(self.rows, 1):
            for c, w in enumerate(row["widgets"]):
                self.grid.addWidget(w, i, c)
        self.add.setEnabled(len(self.rows) < 4)

    def refresh_levels(self):
        for row in self.rows:
            ex = row["ex"]
            if not ex.in_span:
                row["level"].setText("fora da faixa")
            elif not ex.enabled:
                row["level"].setText("desligado")
            else:
                db = ex.rx.signal_db
                row["level"].setText(f"{db:5.0f} dBFS" + (" ●" if ex.rx.squelch.is_open and
                                                          ex.rx.squelch.threshold_db > -150 else ""))


class UpdateController(QObject):
    """Consulta e aplica atualizações do www.pt2vhf.com sem travar a interface."""

    _checked = Signal(object, str, bool)   # info, erro, manual
    _progress = Signal(int, int)
    _downloaded = Signal(object, str)

    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self._dlg = None
        self._checked.connect(self._on_checked)
        self._progress.connect(self._on_progress)
        self._downloaded.connect(self._on_downloaded)

    def check(self, manual: bool = False):
        def run():
            try:
                info = updater.check()
                self._checked.emit(info, "", manual)
            except updater.UpdateError as e:
                self._checked.emit(None, str(e), manual)
        threading.Thread(target=run, daemon=True).start()

    def _on_checked(self, info, err, manual):
        if err:
            if manual:
                QMessageBox.warning(self.win, "Atualizações", err)
            return
        if info is None:
            if manual:
                QMessageBox.information(self.win, "Atualizações",
                                        f"Você já está na versão mais recente ({__version__}).")
            return
        kind = updater.install_kind()
        box = QMessageBox(self.win)
        box.setWindowTitle("Nova versão disponível")
        box.setText(f"<b>PT2VHF SDR Tool {info.version}</b> está disponível (você tem a {__version__}).")
        box.setInformativeText((info.notes or "") + "\n\nDownloads e atualizações oficiais: somente www.pt2vhf.com.")
        can_auto = kind in ("installer", "portable") and info.file is not None
        b_now = box.addButton("Atualizar agora", QMessageBox.AcceptRole) if can_auto else None
        b_page = box.addButton("Abrir página de download", QMessageBox.ActionRole)
        box.addButton("Mais tarde", QMessageBox.RejectRole)
        box.exec()
        if b_now is not None and box.clickedButton() is b_now:
            self._start_download(info, kind)
        elif box.clickedButton() is b_page:
            QDesktopServices.openUrl(QUrl(info.page))

    def _start_download(self, info, kind):
        self._dlg = QProgressDialog("Baixando atualização de www.pt2vhf.com…", None, 0, 100, self.win)
        self._dlg.setWindowModality(Qt.WindowModal)
        self._dlg.setMinimumDuration(0)
        self._dlg.show()

        def run():
            try:
                p = updater.download(info, progress=lambda a, b: self._progress.emit(a, b))
                self._downloaded.emit((p, kind), "")
            except updater.UpdateError as e:
                self._downloaded.emit(None, str(e))
        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, got, total):
        if self._dlg:
            self._dlg.setValue(int(got * 100 / max(total, 1)))

    def _on_downloaded(self, res, err):
        if self._dlg:
            self._dlg.close()
        if err:
            QMessageBox.warning(self.win, "Atualização", err)
            return
        path, kind = res
        try:
            updater.apply(path, kind)
        except updater.UpdateError as e:
            QMessageBox.warning(self.win, "Atualização", str(e))
            return
        self.win.close()
