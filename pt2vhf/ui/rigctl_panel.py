"""Painel CAT com Hamlib rigctld, sem bloquear o thread de interface."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from ..rigctl import RigCtlClient


class RigCtlPanel(QWidget):
    readReceived = Signal(float, str)

    def __init__(self, cfg, current_sdr_tuning, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.current_sdr_tuning = current_sdr_tuning
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pt2vhf-cat")
        self._future = None
        self._action = ""
        layout = QVBoxLayout(self)
        config = QGroupBox("Controle CAT — Hamlib rigctld (externo)")
        form = QFormLayout(config)
        self.host = QLineEdit(str(cfg.get("cat_host", "127.0.0.1")))
        self.host.setMaximumWidth(260)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(cfg.get("cat_port", 4532)))
        self.port.setMaximumWidth(110)
        self.auto = QCheckBox("Seguir automaticamente frequência e modo do rádio (a cada 4 s)")
        self.auto.setChecked(bool(cfg.get("cat_auto_sync", False)))
        self.auto.setToolTip("Somente leitura do rigctld. Nunca transmite PTT nem envia sintonia automaticamente.")
        form.addRow("Host rigctld:", self.host)
        form.addRow("Porta TCP:", self.port)
        form.addRow(self.auto)
        layout.addWidget(config)

        buttons = QHBoxLayout()
        self.get_btn = QPushButton("Ler rádio → SDR")
        self.set_btn = QPushButton("Enviar SDR → rádio")
        self.get_btn.setToolTip("Lê frequência/modo e sintoniza o SDR; não altera o rádio.")
        self.set_btn.setToolTip("Envia apenas frequência/modo por CAT, sem PTT.")
        buttons.addWidget(self.get_btn)
        buttons.addWidget(self.set_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.status = QLabel("Configure o rigctld do rádio. CAT é uma conexão separada do SDR.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        info = QLabel("Requer Hamlib rigctld executado no computador ou rede local, com o modelo e "
                      "a porta serial do transceptor configurados. Esta funcionalidade não instala "
                      "Hamlib nem fornece controle de transmissão. Não exponha a porta CAT à Internet.")
        info.setWordWrap(True)
        info.setObjectName("hintLabel")
        layout.addWidget(info)
        layout.addStretch(1)
        self.get_btn.clicked.connect(lambda: self._run("get"))
        self.set_btn.clicked.connect(lambda: self._run("set"))
        self.host.editingFinished.connect(self._persist)
        self.port.valueChanged.connect(self._persist)
        self.auto.toggled.connect(self._persist)
        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._sync_elapsed = 0

    def _persist(self, *_):
        self.cfg["cat_host"] = self.host.text().strip()
        self.cfg["cat_port"] = int(self.port.value())
        self.cfg["cat_auto_sync"] = self.auto.isChecked()
        self.cfg.save()

    def _run(self, action):
        if self._future is not None:
            return
        try:
            client = RigCtlClient(self.host.text(), self.port.value())
            if action == "set":
                freq, mode = self.current_sdr_tuning()
                self._future = self._pool.submit(client.write, freq, mode)
            else:
                self._future = self._pool.submit(client.read)
            self._action = action
            self.get_btn.setEnabled(False)
            self.set_btn.setEnabled(False)
            self.status.setText("Comunicação CAT em andamento…")
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))

    def _poll(self):
        if self._future is not None and self._future.done():
            f, action = self._future, self._action
            self._future = None
            self.get_btn.setEnabled(True)
            self.set_btn.setEnabled(True)
            try:
                result = f.result()
            except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
                self.status.setText("CAT: " + str(exc))
            else:
                if action == "get":
                    freq, mode = result
                    self.readReceived.emit(freq, mode)
                    self.status.setText(f"Rádio lido: {freq/1e6:.6f} MHz · {mode or 'modo não reconhecido'}")
                else:
                    self.status.setText("Frequência e modo enviados ao rádio. PTT não foi acionado.")
        # Só sincroniza quando a tentativa anterior tiver terminado.
        self._sync_elapsed += 300
        if self._sync_elapsed >= 4000:
            self._sync_elapsed = 0
            if self.auto.isChecked() and self._future is None:
                self._run("get")

    def closeEvent(self, event):
        self.timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)

    def stop(self):
        self.timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
