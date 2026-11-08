"""Painel de decodificação RS41 a partir do IQ do próprio SDR."""
from __future__ import annotations

import time
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QLabel,
    QLineEdit, QDoubleSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QFileDialog, QPlainTextEdit,
)
from ..traffic import Track


class SondeDecoderPanel(QWidget):
    startRequested = Signal(float, str, str)
    stopRequested = Signal()
    captureRequested = Signal(str)

    HEADERS = ("Hora", "Serial", "Latitude", "Longitude", "Altitude m",
               "Vel. km/h", "Vertical m/s", "Detalhes")
    def __init__(self, cfg, current_freq=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.current_freq = current_freq
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
        hz_row = QHBoxLayout()
        hz_row.addWidget(self.frequency)
        self.use_current = QPushButton("Usar sintonia atual do SDR")
        self.use_current.clicked.connect(self._use_current)
        hz_row.addWidget(self.use_current)
        hz_row.addStretch(1)
        f.addRow("Frequência central da sonda:", hz_row)
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
        self.capture = QPushButton("Salvar 20 s IQ (.c16)")
        self.capture.setEnabled(False)
        self.capture.clicked.connect(self._capture)
        row.addWidget(self.capture)
        row.addStretch(1)
        lay.addLayout(row)
        self.status = QLabel("Aguardando. O waterfall sozinho não executa decodificação RS41.")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.diagnostics = QLabel("IQ 0 blocos · quadros 0 · posições 0 · perdidos 0")
        self.diagnostics.setWordWrap(True)
        self.diagnostics.setObjectName("infoLabel")
        lay.addWidget(self.diagnostics)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(100)
        self.log.setMaximumHeight(82)
        self.log.setPlaceholderText("Erros e estatísticas dos decodificadores aparecerão aqui.")
        lay.addWidget(self.log)
        self._last_log = ""
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

    def _use_current(self):
        if self.current_freq is None:
            self.status.setText("Leitura da sintonia atual indisponível.")
            return
        f = float(self.current_freq()) / 1e6
        if 400 <= f <= 406:
            self.frequency.setValue(f)
            self.status.setText(f"Frequência importada da sintonia atual: {f:.6f} MHz")
        else:
            self.status.setText("Sintonize primeiro a radiossonda entre 400 e 406 MHz.")

    def _start(self):
        hz = self.frequency.value() * 1e6
        fsk, decoder = self.fsk_path.text().strip(), self.rs_path.text().strip()
        self.cfg["sonde_iq_hz"] = hz
        self.cfg["sonde_fsk_path"] = fsk
        self.cfg["sonde_rs41_path"] = decoder
        self.cfg.save()
        self.startRequested.emit(hz, fsk, decoder)

    def _capture(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Salvar 20 s de IQ de diagnóstico", "RS41_48kHz_IQ.c16", "IQ int16 complexo (*.c16)")
        if filename:
            self.captureRequested.emit(filename)

    def running(self, on: bool):
        self.start.setEnabled(not on)
        self.stop.setEnabled(on)
        self.capture.setEnabled(on)

    def update_diagnostics(self, data):
        iq, valid, total = data["iq_blocks"], data["positions"], data["json_frames"]
        state = ("processo parado" if not data["fsk_alive"] or not data["decoder_alive"]
                 else "aguardando quadros" if total == 0 else
                 "quadros sem posição" if valid == 0 else "telemetria válida")
        self.diagnostics.setText(
            f"IQ {iq} blocos / {data['iq_samples']:,} amostras · "
            f"JSON {total} · posições {valid} · sem GPS {data['unpositioned_frames']} · "
            f"descartes {data['dropped']} · {state}")
        error = data.get("error") or data.get("demod") or ""
        if error and error != self._last_log:
            self.log.appendPlainText(error)
            self._last_log = error
        if data.get("capture") and data["capture"] != self._last_log:
            self.log.appendPlainText("Amostra IQ salva: " + data["capture"])
            self._last_log = data["capture"]
        if iq and not total and data["fsk_alive"] and data["decoder_alive"]:
            self.status.setText("Sinal IQ recebido; nenhum quadro válido. Verifique ganho, SNR, PPM e versão dos decodificadores.")

    def add_frame(self, data):
        """Mostra quadros RS41 sem GPS para evitar descartes silenciosos."""
        if not isinstance(data, dict):
            return
        row = 0
        self.table.insertRow(row)
        values = (time.strftime("%H:%M:%S"), str(data.get("id", data.get("serial", "—"))),
                  "sem GPS", "sem GPS", "", "", "", "Frame: " + str(data.get("frame", "—")) +
                  " · tipo: " + str(data.get("type", "RS41")))
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))
        if self.table.rowCount() > 300:
            self.table.removeRow(300)

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
