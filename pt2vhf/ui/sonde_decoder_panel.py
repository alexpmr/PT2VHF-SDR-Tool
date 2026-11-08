"""Painel de decodificação RS41 a partir do IQ do próprio SDR."""
from __future__ import annotations

import time
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView,
)
from ..traffic import Track


class SondeDecoderPanel(QWidget):
    startRequested = Signal(float, str, str)
    stopRequested = Signal()

    HEADERS = ("Hora", "Serial", "Latitude", "Longitude", "Altitude m",
               "Vel. km/h", "Vertical m/s", "Detalhes")
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QVBoxLayout(self)
        g = QGroupBox("Decodificar RS41 diretamente do sinal IQ do SDR atual")
        f = QFormLayout(g)
        self.frequency = QDoubleSpinBox()
        self.frequency.setDecimals(6)
        self.frequency.setRange(400.0, 406.0)
        self.frequency.setSingleStep(0.005)
        self.frequency.setSuffix(" MHz")
        self.frequency.setValue(float(cfg.get("sonde_iq_hz", 402_500_000)) / 1e6)
        self.fsk_path = QLineEdit(str(cfg.get("sonde_fsk_path", "")))
        self.rs_path = QLineEdit(str(cfg.get("sonde_rs41_path", "")))
        self.fsk_path.setPlaceholderText("fsk_demod (no PATH ou caminho do executável)")
        self.rs_path.setPlaceholderText("rs41mod (no PATH ou caminho do executável)")
        f.addRow("Frequência central da sonda:", self.frequency)
        f.addRow("Programa fsk_demod:", self.fsk_path)
        f.addRow("Programa rs41mod:", self.rs_path)
        lay.addWidget(g)
        row = QHBoxLayout()
        self.start = QPushButton("Receber e decodificar RS41 via IQ")
        self.stop = QPushButton("Parar decodificação")
        self.stop.setEnabled(False)
        self.start.clicked.connect(self._start)
        self.stop.clicked.connect(self.stopRequested.emit)
        row.addWidget(self.start)
        row.addWidget(self.stop)
        row.addStretch(1)
        lay.addLayout(row)
        self.status = QLabel("Aguardando. O waterfall sozinho não executa decodificação RS41.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        note = QLabel(
            "Requer os binários fsk_demod e rs41mod do projeto radiosonde_auto_rx, instalados "
            "separadamente pelo operador. O SDR Tool reutiliza o IQ do próprio dongle, "
            "sem abrir um segundo receptor. O sinal é convertido a 48 kS/s e decodificado "
            "em processos externos. A implementação atual é somente para RS41 de 400–406 MHz; "
            "outros modelos continuam no backlog. Somente ter energia no waterfall não "
            "garante que o pacote esteja decodificável (modulação, SNR, sinal e sincronização)."
        )
        note.setWordWrap(True)
        note.setObjectName("hintLabel")
        lay.addWidget(note)

    def _start(self):
        hz = self.frequency.value() * 1e6
        fsk, decoder = self.fsk_path.text().strip(), self.rs_path.text().strip()
        self.cfg["sonde_iq_hz"] = hz
        self.cfg["sonde_fsk_path"] = fsk
        self.cfg["sonde_rs41_path"] = decoder
        self.cfg.save()
        self.startRequested.emit(hz, fsk, decoder)

    def running(self, on: bool):
        self.start.setEnabled(not on)
        self.stop.setEnabled(on)

    def add_record(self, track: Track):
        row = 0
        self.table.insertRow(row)
        values = (time.strftime("%H:%M:%S", time.localtime(track.timestamp)),
                  track.ident, f"{track.lat:.5f}", f"{track.lon:.5f}",
                  "" if track.altitude_m is None else f"{track.altitude_m:.0f}",
                  "" if track.speed_kmh is None else f"{track.speed_kmh:.1f}",
                  "" if track.vertical_ms is None else f"{track.vertical_ms:+.1f}",
                  track.details)
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))
        if self.table.rowCount() > 300:
            self.table.removeRow(300)
