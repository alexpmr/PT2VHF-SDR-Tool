"""Recursos de escuta: barra de favoritos, memórias prontas e painel do scanner."""
from __future__ import annotations

import csv
import time
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QListWidget, QListWidgetItem, QMenu, QPushButton, QRadioButton,
                               QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..dsp.receiver import MODES
from ..memory import MemoryChannel
from ..presets import PACKS
from ..scanner import SCAN_PRESETS


# =============================================================================
class FavoritesBar(QWidget):
    """Teclas de memória favoritas (um clique = escutar)."""

    recallRequested = Signal(object)
    addCurrentRequested = Signal()
    unfavoriteRequested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        star = QLabel("★")
        star.setObjectName("favStar")
        lay.addWidget(star)
        self.area = QScrollArea()
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.NoFrame)
        self.area.setFixedHeight(46)
        self.area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.row = QHBoxLayout(self.inner)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(4)
        self.area.setWidget(self.inner)
        lay.addWidget(self.area, 1)
        add = QPushButton("+ Favorito")
        add.setToolTip("Salvar a frequência atual como favorito")
        add.clicked.connect(self.addCurrentRequested)
        lay.addWidget(add)
        self._buttons: list[QToolButton] = []

    def refresh(self, channels: list[MemoryChannel], current_freq: float | None = None):
        for b in self._buttons:
            b.deleteLater()
        self._buttons = []
        while self.row.count():
            self.row.takeAt(0)
        favs = sorted((c for c in channels if c.favorite), key=lambda c: (c.category, c.freq))
        if not favs:
            hint = QLabel("Marque memórias como favoritas (★) para criar teclas de acesso rápido aqui.")
            hint.setObjectName("hintLabel")
            self.row.addWidget(hint)
            self._buttons.append(hint)
        for ch in favs:
            b = QToolButton()
            b.setObjectName("favButton")
            b.setText(f"{ch.name}\n{ch.freq / 1e6:.4f} {ch.mode}")
            b.setToolTip(f"{ch.name} — {ch.freq / 1e6:.5f} MHz {ch.mode}\n{ch.category}  {ch.notes}")
            b.setCheckable(True)
            b.setChecked(current_freq is not None and abs(current_freq - ch.freq) < 1)
            b.clicked.connect(lambda _=False, c=ch: self.recallRequested.emit(c))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, c=ch, btn=b: self._menu(c, btn, pos))
            self.row.addWidget(b)
            self._buttons.append(b)
        self.row.addStretch(1)

    def _menu(self, ch, btn, pos):
        m = QMenu(self)
        m.addAction("Remover dos favoritos", lambda: self.unfavoriteRequested.emit(ch))
        m.exec(btn.mapToGlobal(pos))

    def mark_current(self, freq: float):
        for b in self._buttons:
            if isinstance(b, QToolButton):
                try:
                    f = float(b.text().split("\n")[1].split()[0]) * 1e6
                except (IndexError, ValueError):
                    continue
                b.setChecked(abs(f - freq) < 60)


# =============================================================================
class PresetDialog(QDialog):
    """Escolha de pacotes de memórias prontas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Memórias prontas")
        self.resize(820, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Escolha os pacotes para adicionar às suas memórias. "
                             "Canais já existentes não são duplicados."))
        split = QSplitter()
        self.list = QListWidget()
        for p in PACKS:
            it = QListWidgetItem(f"{p.name}  ({len(p.channels)})")
            it.setData(Qt.UserRole, p.key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.list.addItem(it)
        split.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        rl.addWidget(self.desc)
        self.preview = QTableWidget(0, 4)
        self.preview.setHorizontalHeaderLabels(["Nome", "MHz", "Modo", "Notas"])
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        rl.addWidget(self.preview, 1)
        split.addWidget(right)
        split.setSizes([300, 520])
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        allb = QPushButton("Marcar todos")
        allb.clicked.connect(lambda: [self.list.item(i).setCheckState(Qt.Checked) for i in range(self.list.count())])
        row.addWidget(allb)
        self.fav = QCheckBox("Marcar os canais importados como favoritos")
        row.addWidget(self.fav)
        row.addStretch(1)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Importar")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.list.currentRowChanged.connect(self._show)
        self.list.setCurrentRow(0)

    def _show(self, row):
        if row < 0:
            return
        p = PACKS[row]
        self.desc.setText(f"<b>{p.name}</b> → categoria <i>{p.category}</i><br>{p.description}")
        self.preview.setRowCount(0)
        for c in p.channels:
            r = self.preview.rowCount()
            self.preview.insertRow(r)
            for k, v in enumerate((c.name, f"{c.freq / 1e6:.5f}", c.mode, c.notes)):
                self.preview.setItem(r, k, QTableWidgetItem(v))

    def selected_keys(self) -> list[str]:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.Checked]


# =============================================================================
RESOLUTIONS = [1000, 2500, 5000, 6250, 10000, 12500, 25000, 100000]


class ScannerPanel(QWidget):
    startRequested = Signal(dict)
    stopRequested = Signal()
    listenRequested = Signal(float, str, float)      # freq, modo, largura
    saveRequested = Signal(list, str)                # [freqs], categoria
    lockoutRequested = Signal(list)
    clearLockouts = Signal()
    clearHits = Signal()
    autoRecordChanged = Signal(bool, float)
    priorityFromCurrent = Signal()

    HIT_COLS = ["Frequência (MHz)", "Memória", "Acessos", "Última vez", "SNR máx. (dB)", "Tempo ativo (s)", "Escutado"]
    ACT_COLS = ["Hora", "Frequência (MHz)", "Memória", "Modo", "Duração (s)", "Arquivo", "Transcrição"]

    def __init__(self, cfg, categories: list[str], parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # ---------------------------------------------------------- aba varredura
        w = QWidget()
        wl = QHBoxLayout(w)
        left = QVBoxLayout()
        g = QGroupBox("Faixa")
        f = QFormLayout(g)
        self.preset = QComboBox()
        for p in SCAN_PRESETS:
            self.preset.addItem(p.name + (f"  — {p.notes}" if p.notes else ""), p)
        self.preset.addItem("Personalizada", None)
        f.addRow(self.preset)
        rr = QHBoxLayout()
        self.f0 = QDoubleSpinBox()
        self.f1 = QDoubleSpinBox()
        for s in (self.f0, self.f1):
            s.setRange(0.024, 1766)
            s.setDecimals(4)
            s.setSuffix(" MHz")
        rr.addWidget(self.f0)
        rr.addWidget(QLabel("até"))
        rr.addWidget(self.f1)
        f.addRow("De:", rr)
        self.res = QComboBox()
        for r in RESOLUTIONS:
            self.res.addItem(f"{r / 1000:g} kHz", r)
        f.addRow("Resolução:", self.res)
        self.mode = QComboBox()
        self.mode.addItems(list(MODES))
        self.bw = QDoubleSpinBox()
        self.bw.setRange(0.1, 200)
        self.bw.setSuffix(" kHz")
        mr = QHBoxLayout()
        mr.addWidget(self.mode)
        mr.addWidget(self.bw)
        f.addRow("Escutar em:", mr)
        self.snr = QSpinBox()
        self.snr.setRange(3, 40)
        self.snr.setSuffix(" dB acima do ruído")
        f.addRow("Sensibilidade:", self.snr)
        left.addWidget(g)

        g = QGroupBox("Ação ao encontrar sinal")
        f = QFormLayout(g)
        self.only_discover = QRadioButton("Só descobrir (registra e continua)")
        self.stop_listen = QRadioButton("Parar e escutar")
        grp = QButtonGroup(self)
        grp.addButton(self.only_discover)
        grp.addButton(self.stop_listen)
        self.stop_listen.setChecked(True)
        f.addRow(self.only_discover)
        f.addRow(self.stop_listen)
        self.resume = QDoubleSpinBox()
        self.resume.setRange(0.5, 30)
        self.resume.setValue(2.0)
        self.resume.setSuffix(" s")
        f.addRow("Retomar após silêncio:", self.resume)
        self.max_listen = QSpinBox()
        self.max_listen.setRange(0, 600)
        self.max_listen.setSuffix(" s  (0 = sem limite)")
        f.addRow("Tempo máx. no canal:", self.max_listen)
        pr = QHBoxLayout()
        self.prio_on = QCheckBox()
        self.prio = QDoubleSpinBox()
        self.prio.setRange(0.024, 1766)
        self.prio.setDecimals(4)
        self.prio.setSuffix(" MHz")
        self.prio.setValue(156.8)
        self.prio_btn = QPushButton("Atual")
        self.prio_btn.setToolTip("Usar a frequência atual como prioritária")
        pr.addWidget(self.prio_on)
        pr.addWidget(self.prio, 1)
        pr.addWidget(self.prio_btn)
        f.addRow("Canal prioritário:", pr)
        self.prio_int = QDoubleSpinBox()
        self.prio_int.setRange(1, 60)
        self.prio_int.setValue(3)
        self.prio_int.setSuffix(" s")
        f.addRow("Verificar prioridade a cada:", self.prio_int)
        left.addWidget(g)

        br = QHBoxLayout()
        self.start = QPushButton("▶ Iniciar varredura")
        self.start.setCheckable(True)
        self.start.setObjectName("powerButton")
        self.start.setMinimumHeight(32)
        br.addWidget(self.start)
        left.addLayout(br)
        self.status = QLabel("Parado")
        self.status.setObjectName("infoLabel")
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        left.addStretch(1)
        lw = QWidget()
        lw.setLayout(left)
        lw.setMaximumWidth(420)
        wl.addWidget(lw)

        right = QVBoxLayout()
        self.hits = QTableWidget(0, len(self.HIT_COLS))
        self.hits.setHorizontalHeaderLabels(self.HIT_COLS)
        self.hits.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.hits.horizontalHeader().setStretchLastSection(True)
        self.hits.setColumnWidth(1, 170)
        self.hits.verticalHeader().setVisible(False)
        self.hits.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.hits.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.hits.setSortingEnabled(True)
        right.addWidget(QLabel("Frequências ativas encontradas (duplo clique para escutar):"))
        right.addWidget(self.hits, 1)
        hb = QHBoxLayout()
        self.b_listen = QPushButton("Escutar")
        self.cat = QComboBox()
        self.cat.setEditable(True)
        self.cat.addItems(categories)
        self.cat.setCurrentText("Descobertas")
        self.b_save = QPushButton("Salvar como memória →")
        self.b_lock = QPushButton("Bloquear")
        self.b_lock.setToolTip("Ignorar estas frequências (ruído, interferência)")
        self.b_unlock = QPushButton("Desbloquear todas")
        self.b_clear = QPushButton("Limpar")
        self.b_export = QPushButton("Exportar CSV")
        for x in (self.b_listen, self.b_save, self.cat, self.b_lock, self.b_unlock, self.b_clear, self.b_export):
            hb.addWidget(x)
        hb.insertStretch(3, 0)
        right.addLayout(hb)
        wl.addLayout(right, 1)
        self.tabs.addTab(w, "Varredura")

        # ---------------------------------------------------------- aba atividade
        a = QWidget()
        al = QVBoxLayout(a)
        top = QHBoxLayout()
        self.autorec = QCheckBox("Gravar automaticamente cada transmissão (quando o squelch abre)")
        self.min_dur = QDoubleSpinBox()
        self.min_dur.setRange(0.2, 30)
        self.min_dur.setValue(1.0)
        self.min_dur.setSuffix(" s mín.")
        open_folder = QPushButton("Abrir pasta")
        open_folder.clicked.connect(self._open_folder)
        top.addWidget(self.autorec)
        top.addWidget(self.min_dur)
        self.transcribe = QCheckBox("Transcrever fonia (local, opcional)")
        self.transcribe.setToolTip("Converte cada gravação em texto no próprio computador (faster-whisper) "
                                   "e destaca os indicativos ouvidos")
        top.addWidget(self.transcribe)
        top.addStretch(1)
        top.addWidget(open_folder)
        al.addLayout(top)
        self.act = QTableWidget(0, len(self.ACT_COLS))
        self.act.setHorizontalHeaderLabels(self.ACT_COLS)
        self.act.horizontalHeader().setStretchLastSection(True)
        self.act.verticalHeader().setVisible(False)
        self.act.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.act.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.act.setColumnWidth(2, 170)
        self.act.setColumnWidth(5, 230)
        al.addWidget(self.act, 1)
        ab = QHBoxLayout()
        play = QPushButton("▶ Ouvir")
        play.clicked.connect(self._play)
        clr = QPushButton("Limpar lista")
        clr.clicked.connect(lambda: self.act.setRowCount(0))
        self.act_info = QLabel("")
        ab.addWidget(play)
        ab.addWidget(self.act_info, 1)
        ab.addWidget(clr)
        al.addLayout(ab)
        self.tabs.addTab(a, "Atividade gravada")

        # ---------------------------------------------------------- ligações
        self.preset.currentIndexChanged.connect(self._preset)
        self.start.toggled.connect(self._toggle)
        self.hits.itemDoubleClicked.connect(lambda *_: self._listen())
        self.b_listen.clicked.connect(self._listen)
        self.b_save.clicked.connect(lambda: self.saveRequested.emit(self._selected_freqs(), self.cat.currentText()))
        self.b_lock.clicked.connect(lambda: self.lockoutRequested.emit(self._selected_freqs()))
        self.b_unlock.clicked.connect(self.clearLockouts)
        self.b_clear.clicked.connect(self.clearHits)
        self.b_export.clicked.connect(self._export)
        self.prio_btn.clicked.connect(self.priorityFromCurrent)
        self.autorec.toggled.connect(lambda v: self.autoRecordChanged.emit(v, self.min_dur.value()))
        self.min_dur.valueChanged.connect(lambda v: self.autoRecordChanged.emit(self.autorec.isChecked(), v))
        self.act.itemDoubleClicked.connect(lambda *_: self._play())
        self._preset(0)

    # ---------------------------------------------------------- helpers
    def _preset(self, idx):
        p = self.preset.itemData(idx)
        if p is None:
            return
        self.f0.setValue(p.start / 1e6)
        self.f1.setValue(p.end / 1e6)
        i = self.res.findData(p.resolution)
        self.res.setCurrentIndex(i if i >= 0 else 2)
        self.mode.setCurrentText(p.mode)
        self.bw.setValue(p.bandwidth / 1000)
        self.snr.setValue(int(p.snr_db))

    def options(self) -> dict:
        return {
            "start": self.f0.value() * 1e6, "end": self.f1.value() * 1e6,
            "resolution": self.res.currentData(), "snr_db": float(self.snr.value()),
            "mode": self.mode.currentText(), "bandwidth": self.bw.value() * 1000,
            "listen": self.stop_listen.isChecked(), "resume_s": self.resume.value(),
            "max_listen_s": float(self.max_listen.value()),
            "priority_freq": self.prio.value() * 1e6 if self.prio_on.isChecked() else None,
            "priority_interval_s": self.prio_int.value(),
        }

    def _toggle(self, on):
        if on:
            self.startRequested.emit(self.options())
        else:
            self.stopRequested.emit()

    def set_running(self, on: bool):
        self.start.blockSignals(True)
        self.start.setChecked(on)
        self.start.setText("■ Parar varredura" if on else "▶ Iniciar varredura")
        self.start.blockSignals(False)

    def _selected_freqs(self) -> list[float]:
        rows = {i.row() for i in self.hits.selectedItems()}
        out = []
        for r in sorted(rows):
            it = self.hits.item(r, 0)
            if it:
                out.append(float(it.data(Qt.UserRole)))
        return out

    def _listen(self):
        fs = self._selected_freqs()
        if fs:
            self.listenRequested.emit(fs[0], self.mode.currentText(), self.bw.value() * 1000)

    def show_hits(self, hits, mem_lookup, now: float):
        """Atualiza a tabela (mantém a seleção)."""
        sel = set(self._selected_freqs())
        self.hits.setSortingEnabled(False)
        self.hits.setRowCount(len(hits))
        for r, h in enumerate(hits):
            ago = now - h.last_seen
            vals = [f"{h.freq / 1e6:.4f}", mem_lookup(h.freq), h.hits,
                    "agora" if ago < 1.5 else f"há {ago:.0f} s" if ago < 120 else time.strftime("%H:%M", time.localtime(time.time() - ago)),
                    round(h.max_snr, 1), round(h.seconds_active, 1), "✓" if h.listened else ""]
            for c, v in enumerate(vals):
                it = _NumItem(v)
                if c == 0:
                    it.setData(Qt.UserRole, h.freq)
                self.hits.setItem(r, c, it)
            if h.freq in sel:
                self.hits.selectRow(r)
        self.hits.setSortingEnabled(True)

    def add_activity(self, ev: dict, mem_name: str):
        self.act.insertRow(0)
        vals = [time.strftime("%H:%M:%S", time.localtime(ev["start"])), f"{ev['freq'] / 1e6:.4f}", mem_name,
                ev["mode"], f"{ev['duration']:.1f}", Path(ev["file"]).name]
        for c, v in enumerate(vals):
            it = QTableWidgetItem(v)
            if c == 5:
                it.setData(Qt.UserRole, ev["file"])
            self.act.setItem(0, c, it)
        self.act_info.setText(f"{self.act.rowCount()} gravações")

    def set_transcription(self, path: str, text: str, calls: list):
        for r in range(self.act.rowCount()):
            it = self.act.item(r, 5)
            if it and it.data(Qt.UserRole) == path:
                label = (f"[{', '.join(calls)}] " if calls else "") + (text or "(sem fala reconhecida)")
                cell = QTableWidgetItem(label)
                cell.setToolTip(text)
                self.act.setItem(r, 6, cell)
                return

    def _play(self):
        r = self.act.currentRow()
        if r < 0:
            return
        f = self.act.item(r, 5).data(Qt.UserRole)
        QDesktopServices.openUrl(QUrl.fromLocalFile(f))

    def _open_folder(self):
        p = Path(self.cfg["recordings_dir"]) / "atividade"
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Exportar frequências ativas", "scanner.csv", "CSV (*.csv)")
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(self.HIT_COLS)
            for r in range(self.hits.rowCount()):
                w.writerow([self.hits.item(r, c).text() for c in range(self.hits.columnCount())])


class _NumItem(QTableWidgetItem):
    """Ordena numericamente quando possível."""

    def __init__(self, v):
        super().__init__(str(v))
        self._v = v

    def __lt__(self, other):
        a, b = self._v, getattr(other, "_v", other.text())
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return str(a) < str(b)



