"""Interface dos recursos da v0.3: assistente de sintonia, voltar no tempo, receptores extras
e atualização pelo site oficial."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
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
    """OTA no padrão dos programas PT2VHF (Sat Tool): verificação automática, instalação automática
    quando o programa está livre (opção padrão) ou pergunta "Atualizar agora / Depois" (adia 24 h)."""

    RETRY_FAIL_S = 6 * 3600
    SNOOZE_S = 24 * 3600
    _checked = Signal(object, str, bool)
    _progress = Signal(int, int)
    _downloaded = Signal(object, str)

    def __init__(self, window, button: QPushButton):
        super().__init__(window)
        self.win = window
        self.btn = button
        self.kind = updater.install_kind()
        self.available = None
        self._dlg = None
        self._busy_download = False
        self._prompted = ""
        self._silent = False
        self._checked.connect(self._on_checked)
        self._progress.connect(self._on_progress)
        self._downloaded.connect(self._on_downloaded)
        self.btn.setText(f"v{__version__}")
        self.btn.setToolTip("Verificar versões em www.pt2vhf.com e atualizar")
        self.btn.clicked.connect(self.on_button)

    # ------------------------------------------------------------ consulta
    def check(self, manual: bool = False):
        if self.kind == "source" and not manual:
            return

        def run():
            try:
                info = updater.check(self.kind if self.kind != "source" else "installer")
                self._checked.emit(info, "", manual)
            except updater.UpdateError as e:
                self._checked.emit(None, str(e), manual)
        threading.Thread(target=run, daemon=True).start()

    def on_button(self):
        if self.available is not None and self.available.file is not None and self.kind != "source":
            self.start(silent=False)
        else:
            self.check(manual=True)

    def _cfg(self):
        return self.win.cfg

    def _on_checked(self, info, err, manual):
        if err:
            if manual:
                QMessageBox.warning(self.win, "Atualizações", err)
            return
        self.available = info
        if info is None:
            self.btn.setText(f"v{__version__}")
            if manual:
                QMessageBox.information(self.win, "Atualizações",
                                        f"Você já está na versão mais recente ({__version__}).")
            return
        self.btn.setText(f"Nova versão {info.version} · atualizar")
        if self.kind == "source" or info.file is None:
            if manual:
                QMessageBox.information(self.win, "Atualizações",
                                        f"A versão {info.version} está disponível em {info.page}.")
                QDesktopServices.openUrl(QUrl(info.page))
            return
        if manual:
            self.start(silent=False)
        elif self._cfg().get("auto_update", True):
            self.try_auto()
        else:
            self.maybe_prompt()

    # ------------------------------------------------------------ automático / pergunta
    def try_auto(self):
        info = self.available
        if info is None or self._busy_download:
            return
        failed = self._cfg().get("update_failed") or {}
        if failed.get("version") == info.version and time.time() - float(failed.get("at") or 0) < self.RETRY_FAIL_S:
            return
        busy = self.win.operation_busy()
        if busy:
            self.btn.setText(f"Nova versão {info.version} · instala ao ficar livre")
            self.btn.setToolTip("Atualização automática adiada: " + busy)
            QTimer.singleShot(60_000, self.try_auto)
            return
        self.start(silent=True)

    def maybe_prompt(self):
        info = self.available
        if info is None or self._busy_download or self._prompted == info.version:
            return
        snooze = self._cfg().get("update_prompt_snooze") or {}
        if snooze.get("version") == info.version and time.time() - float(snooze.get("at") or 0) < self.SNOOZE_S:
            return
        from PySide6.QtWidgets import QApplication
        if QApplication.activeModalWidget() is not None:
            QTimer.singleShot(5000, self.maybe_prompt)
            return
        self._prompted = info.version
        box = QMessageBox(self.win)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Nova versão disponível")
        box.setText(f"PT2VHF SDR Tool {info.version} está disponível (instalada: {__version__}).\n\n"
                    "Deseja atualizar agora?")
        now = box.addButton("Atualizar agora", QMessageBox.AcceptRole)
        box.addButton("Depois", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is now:
            self.start(silent=False)
        else:
            self._cfg()["update_prompt_snooze"] = {"version": info.version, "at": time.time()}
            self._cfg().save()

    # ------------------------------------------------------------ download e instalação
    def start(self, silent: bool):
        info = self.available
        if info is None or info.file is None or self._busy_download:
            return
        self._busy_download, self._silent = True, silent
        if not silent:
            self._dlg = QProgressDialog("Baixando e verificando atualização de www.pt2vhf.com…", None, 0, 100, self.win)
            self._dlg.setWindowModality(Qt.WindowModal)
            self._dlg.setMinimumDuration(0)
            self._dlg.show()
        self.btn.setText("Atualização em andamento…")

        def run():
            try:
                p = updater.download(info, progress=lambda a, b: self._progress.emit(a, b))
                self._downloaded.emit(p, "")
            except updater.UpdateError as e:
                self._downloaded.emit(None, str(e))
        threading.Thread(target=run, daemon=True).start()

    def _on_progress(self, got, total):
        pct = min(99, int(got * 100 / max(total, 1)))
        if self._dlg:
            self._dlg.setValue(pct)
        if self._silent:
            self.btn.setText(f"Atualizando para {self.available.version}… {pct}%")

    def _on_downloaded(self, path, err):
        self._busy_download = False
        if self._dlg:
            self._dlg.close()
            self._dlg = None
        if err:
            self.btn.setText("Falha ao atualizar · tentar novamente")
            self._cfg()["update_failed"] = {"version": self.available.version, "at": time.time()}
            self._cfg().save()
            if not self._silent:
                QMessageBox.warning(self.win, "Atualização", err)
            return
        try:
            updater.apply(path, self.kind, self.available.version)
        except updater.UpdateError as e:
            QMessageBox.critical(self.win, "Atualização não aplicada", str(e))
            return
        self.win.quit_for_update()

    # ------------------------------------------------------------ resultado da anterior
    def show_last_result(self):
        res = updater.read_update_result()
        if not res:
            return
        status, version, detail = res
        if status == "ok":
            QMessageBox.information(self.win, "Atualização concluída",
                                    f"PT2VHF SDR Tool atualizado para a versão {version or __version__}.")
        else:
            QMessageBox.warning(self.win, "Atualização não concluída",
                                f"A atualização não terminou: {detail}\n\nBaixe a versão nova em "
                                "www.pt2vhf.com/sdr ou tente de novo pelo botão de versão.")


def show_welcome(parent):
    """Anúncio de abertura (padrão dos programas PT2VHF): convite às demais aplicações e ao site."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox
    dlg = QDialog(parent)
    dlg.setWindowTitle("PT2VHF SDR Tool")
    lay = QVBoxLayout(dlg)
    title = QLabel("Feito por radioamadores, para radioamadores")
    title.setStyleSheet("font-size:18px;font-weight:700")
    text = QLabel("Obrigado por usar o PT2VHF SDR Tool! Conheça também as outras aplicações gratuitas "
                  "desenvolvidas para a comunidade: APRS Client, APRS Android, Prop Tool, Mesh Analyzer, "
                  "Sat Tool, Prog Tool, QSL Manager e mais. Downloads e atualizações oficiais somente pelo site.")
    text.setWordWrap(True)
    link = QLabel('<a href="https://www.pt2vhf.com" style="color:#6cc7ff;font-weight:700">www.PT2VHF.com</a>')
    link.setOpenExternalLinks(True)
    bb = QDialogButtonBox()
    close = bb.addButton("Fechar", QDialogButtonBox.RejectRole)
    close.setDefault(True)
    bb.rejected.connect(dlg.reject)
    for w in (title, text, link):
        lay.addWidget(w)
    lay.addWidget(bb)
    dlg.setMinimumWidth(520)
    dlg.exec()
