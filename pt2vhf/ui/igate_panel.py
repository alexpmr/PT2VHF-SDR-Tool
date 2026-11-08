"""iGate APRS RF -> APRS-IS somente RX. Exige ação explícita e passcode do operador."""
from __future__ import annotations

import queue
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from .. import __version__
from ..aprs_igate import ReceiveOnlyIGate


class IGatePanel(QWidget):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.worker = None
        self.messages = queue.SimpleQueue()
        root = QVBoxLayout(self)
        group = QGroupBox("APRS iGate RF → APRS-IS, somente RX")
        form = QFormLayout(group)
        self.call = QLineEdit(cfg.get("my_callsign", ""))
        self.call.setMaximumWidth(160)
        self.passcode = QLineEdit()
        self.passcode.setEchoMode(QLineEdit.Password)
        self.passcode.setMaximumWidth(120)
        self.passcode.setPlaceholderText("Não é salvo")
        self.host = QLineEdit(cfg.get("igate_host", "rotate.aprs2.net"))
        self.host.setMaximumWidth(240)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(cfg.get("igate_port", 14580)))
        self.port.setMaximumWidth(120)
        form.addRow("Indicativo do iGate:", self.call)
        form.addRow("Passcode APRS-IS:", self.passcode)
        form.addRow("Servidor:", self.host)
        form.addRow("Porta:", self.port)
        root.addWidget(group)
        row = QHBoxLayout()
        self.start = QPushButton("Ativar iGate RX (envio ao APRS-IS)")
        self.start.clicked.connect(self.toggle)
        row.addWidget(self.start)
        row.addStretch(1)
        root.addLayout(row)
        self.status = QLabel("Desativado. Nenhum pacote é enviado à Internet.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        text = QLabel(
            "Somente pacotes decodificados de RF físico (RTL-SDR, rtl_tcp, SoapySDR). "
            "Não faz transmissão por rádio nem recebe pacotes APRS-IS para RF. "
            "Usa qAO para indicar iGate RX-only; filtra NOGATE/RFONLY/TCPIP "
            "e duplicatas. Requer indicativo e passcode verificado. "
            "Não armazena o passcode. Somente ative onde tiver autorização para operar."
        )
        text.setWordWrap(True)
        text.setObjectName("hintLabel")
        root.addWidget(text)
        root.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_status)
        self.timer.start()

    def toggle(self):
        if self.worker is not None:
            self.stop()
            return
        try:
            worker = ReceiveOnlyIGate(self.call.text(), self.passcode.text(),
                                      self.host.text(), self.port.value(),
                                      software_version=__version__, on_status=self.messages.put)
        except ValueError as exc:
            QMessageBox.warning(self, "APRS iGate", str(exc))
            return
        self.cfg["igate_host"] = self.host.text().strip()
        self.cfg["igate_port"] = self.port.value()
        self.cfg.save()
        self.worker = worker
        self.start.setText("Desativar iGate RX")
        self.status.setText("Conectando ao APRS-IS…")
        self.passcode.clear()
        worker.start()

    def submit_rf(self, packet):
        if self.worker is not None:
            self.worker.submit(packet.raw)

    def update_status(self):
        while not self.messages.empty():
            try:
                text = self.messages.get_nowait()
                self.status.setText(text)
            except queue.Empty:
                break
        if self.worker is not None:
            a = self.worker
            flag = "conectado" if a.verified else "sem autenticação"
            self.start.setToolTip(f"APRS-IS {flag} · {a.sent} enviados · {a.dropped} descartados")

    def stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.start.setText("Ativar iGate RX (envio ao APRS-IS)")
        self.status.setText("iGate desativado; nenhum envio à Internet.")

    def closeEvent(self, event):
        self.stop()
        self.timer.stop()
        super().closeEvent(event)
