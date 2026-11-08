"""Satélite por TLE: previsão de passagens e correção RX Doppler opcional.

Sem consulta automática de órbitas: o radioamador fornece TLE atualizado.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QDoubleSpinBox,
)

from ..decoders.aprs import locator_to_latlon
from ..satellites import look_angle, next_passes, parse_tles, receive_doppler_hz


class SatellitePanel(QWidget):
    tuneReceiveRequested = Signal(float)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.satellites = []
        root = QVBoxLayout(self)

        p = QGroupBox("Órbitas TLE — dados fornecidos pelo usuário")
        grid = QGridLayout(p)
        self.path = QLineEdit(cfg.get("sat_tle_path", ""))
        self.path.setPlaceholderText("Selecione um arquivo TLE (ex.: ISS, NOAA, Meteor)")
        browse = QPushButton("Abrir TLE…")
        browse.clicked.connect(self._open_tle)
        grid.addWidget(QLabel("Arquivo:"), 0, 0)
        grid.addWidget(self.path, 0, 1)
        grid.addWidget(browse, 0, 2)
        self.choose = QComboBox()
        self.choose.currentIndexChanged.connect(self.refresh)
        grid.addWidget(QLabel("Satélite:"), 1, 0)
        grid.addWidget(self.choose, 1, 1, 1, 2)
        root.addWidget(p)

        p2 = QGroupBox("Estação de recepção e Doppler")
        f = QGridLayout(p2)
        self.locator = QLineEdit(cfg.get("my_locator", ""))
        self.locator.setMaximumWidth(120)
        self.freq = QDoubleSpinBox()
        self.freq.setRange(0.001, 1766.0)
        self.freq.setDecimals(6)
        self.freq.setSuffix(" MHz")
        self.freq.setValue(float(cfg.get("sat_nominal_hz", 145800000)) / 1e6)
        self.freq.setSingleStep(0.005)
        self.freq.setToolTip("Frequência nominal do downlink; ajuste somente em recepção")
        self.follow = QCheckBox("Corrigir Doppler automaticamente quando acima do horizonte")
        self.follow.setChecked(bool(cfg.get("sat_doppler_auto", False)))
        self.follow.setToolTip("Aplica sintonia RX a cada 5 s; desative para usar sintonia manual.")
        f.addWidget(QLabel("Locator:"), 0, 0)
        f.addWidget(self.locator, 0, 1)
        f.addWidget(QLabel("Downlink:"), 0, 2)
        f.addWidget(self.freq, 0, 3)
        f.addWidget(self.follow, 1, 0, 1, 4)
        self.summary = QLabel("Selecione um TLE para consultar a órbita.")
        self.summary.setWordWrap(True)
        f.addWidget(self.summary, 2, 0, 1, 4)
        tune = QPushButton("Aplicar frequência RX corrigida agora")
        tune.clicked.connect(self._tune_now)
        self._last_freq = None
        f.addWidget(tune, 3, 0, 1, 4)
        root.addWidget(p2)

        row = QHBoxLayout()
        calc = QPushButton("Calcular passagens nas próximas 24 h")
        calc.clicked.connect(self.calculate_passes)
        row.addWidget(calc)
        row.addStretch(1)
        root.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("AOS (local)", "Pico (local)", "LOS (local)", "Elevação máxima"))
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        note = QLabel("Propagação SGP4 aproximada (TLE); órbitas envelhecidas geram erros. "
                      "Somente RX: não transmite, não controla rotor, não faz download de TLE, "
                      "não substitui o rastreamento satelital de precisão.")
        note.setWordWrap(True)
        note.setObjectName("hintLabel")
        root.addWidget(note)

        self.path.editingFinished.connect(self._load_from_path)
        for w in (self.freq, self.locator, self.follow):
            sig = w.valueChanged if w is self.freq else (w.textChanged if w is self.locator else w.toggled)
            sig.connect(self._persist)
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self._load_from_path()

    def _persist(self, *_):
        self.cfg["sat_tle_path"] = self.path.text().strip()
        self.cfg["sat_nominal_hz"] = self.freq.value() * 1e6
        self.cfg["sat_doppler_auto"] = self.follow.isChecked()
        self.cfg.save()

    def _open_tle(self):
        path, _ = QFileDialog.getOpenFileName(self, "Arquivo TLE", self.path.text(),
                                              "TLE (*.tle *.txt);;Todos (*.*)")
        if path:
            self.path.setText(path)
            self._load_from_path()

    def _load_from_path(self):
        self._persist()
        path = self.path.text().strip()
        if not path:
            return
        try:
            file = Path(path).expanduser()
            if file.stat().st_size > 1_000_000:
                raise ValueError("Arquivo TLE maior que 1 MB")
            sats = parse_tles(file.read_text(encoding="utf-8-sig"))
            if not sats:
                raise ValueError("Nenhum par de linhas TLE válido")
        except (OSError, UnicodeError, ValueError) as exc:
            self.summary.setText(f"TLE inválido ou indisponível: {exc}")
            return
        old = self.choose.currentText()
        self.satellites = sats
        self.choose.clear()
        self.choose.addItems([s.name for s in sats])
        ix = self.choose.findText(old)
        if ix >= 0:
            self.choose.setCurrentIndex(ix)
        self.refresh()

    def _selected(self):
        index = self.choose.currentIndex()
        if 0 <= index < len(self.satellites):
            return self.satellites[index]
        return None

    def _position(self):
        coord = locator_to_latlon(self.locator.text().strip())
        if coord is None:
            raise ValueError("Informe um locator Maidenhead válido (ex.: GH64cd)")
        return coord

    def refresh(self, *_):
        sat = self._selected()
        if sat is None:
            return
        try:
            lat, lon = self._position()
            now = dt.datetime.now(dt.timezone.utc)
            p = look_angle(sat, lat, lon, now)
            shift = receive_doppler_hz(self.freq.value() * 1e6, p.range_rate_km_s)
            tuned = self.freq.value() * 1e6 + shift
            self._last_freq = tuned
            state = "acima do horizonte" if p.el_deg >= 0 else "abaixo do horizonte"
            self.summary.setText(
                f"{sat.name}: az {p.az_deg:.1f}°, elevação {p.el_deg:.1f}° ({state}), "
                f"distância {p.range_km:.0f} km, radial {p.range_rate_km_s:+.3f} km/s. "
                f"Doppler RX {shift:+.0f} Hz · sintonizar {tuned/1e6:.6f} MHz")
            if self.follow.isChecked() and p.el_deg > 0:
                self.tuneReceiveRequested.emit(tuned)
        except (RuntimeError, ValueError) as exc:
            self.summary.setText(f"Satélite: {exc}")

    def _tune_now(self):
        self.refresh()
        if self._last_freq is not None:
            self.tuneReceiveRequested.emit(self._last_freq)

    def calculate_passes(self):
        sat = self._selected()
        if sat is None:
            QMessageBox.information(self, "TLE", "Carregue um arquivo TLE.")
            return
        try:
            lat, lon = self._position()
            events = next_passes(sat, lat, lon, dt.datetime.now(dt.timezone.utc), hours=24)
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Passagens", str(exc))
            return
        self.table.setRowCount(len(events))
        for i, event in enumerate(events):
            for col, value in enumerate((
                event["aos"].astimezone().strftime("%d/%m %H:%M:%S"),
                event["peak"].astimezone().strftime("%d/%m %H:%M:%S"),
                event["los"].astimezone().strftime("%d/%m %H:%M:%S"),
                f'{event["max_el"]:.1f}°')):
                self.table.setItem(i, col, QTableWidgetItem(value))
        if not events:
            self.summary.setText("Sem passagens acima do horizonte nas próximas 24 h.")
