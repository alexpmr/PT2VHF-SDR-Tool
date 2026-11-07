"""Aba Configurações: geral, atualizações, interface web (local/LAN) e receptor."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)


class SettingsPanel(QWidget):
    changed = Signal(str, object)        # chave, valor
    checkUpdatesNow = Signal()
    webApply = Signal()
    webOpen = Signal()
    webCopy = Signal()

    def __init__(self, cfg, levels, themes, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        lay = QHBoxLayout(self)
        col1, col2 = QVBoxLayout(), QVBoxLayout()
        lay.addLayout(col1, 1)
        lay.addLayout(col2, 1)

        g = QGroupBox("Geral")
        f = QFormLayout(g)
        self.call = QLineEdit(cfg.get("my_callsign", ""))
        self.locator = QLineEdit(cfg.get("my_locator", ""))
        self.rec_dir = QLineEdit(cfg.get("recordings_dir", ""))
        browse = QPushButton("…")
        browse.setFixedWidth(30)
        rr = QHBoxLayout()
        rr.addWidget(self.rec_dir, 1)
        rr.addWidget(browse)
        self.level = QComboBox()
        self.level.addItems(levels)
        self.level.setCurrentText(cfg.get("ui_level", "Intermediário"))
        self.theme = QComboBox()
        self.theme.addItems(themes)
        self.theme.setCurrentText(cfg.get("lcd_theme", themes[0]))
        f.addRow("Indicativo:", self.call)
        f.addRow("Locator (grid):", self.locator)
        f.addRow("Pasta de gravações:", rr)
        f.addRow("Nível da interface:", self.level)
        f.addRow("Tema do display:", self.theme)
        col1.addWidget(g)

        g = QGroupBox("Sintonia e receptor")
        f = QFormLayout(g)
        self.auto_tune = QCheckBox("Auto-sintonizar ao selecionar uma transmissão (tecla A-SINT)")
        self.auto_tune.setChecked(bool(cfg.get("auto_tune", True)))
        self.smeter = QDoubleSpinBox()
        self.smeter.setRange(-60, 60)
        self.smeter.setSuffix(" dB")
        self.smeter.setValue(float(cfg.get("s_meter_cal", 0.0)))
        self.smeter.setToolTip("Somado à leitura do S-meter para calibrar com um gerador ou rádio de referência")
        self.rtl_lib = QComboBox()
        for label, val in (("Automático (RTL-SDR Blog; se não abrir, a padrão)", "auto"),
                           ("Driver RTL-SDR Blog (V4, HF pelo conversor)", "blog"),
                           ("Padrão (como na 0.3.0)", "standard")):
            self.rtl_lib.addItem(label, val)
        i = self.rtl_lib.findData(cfg.get("rtl_library", "auto"))
        self.rtl_lib.setCurrentIndex(max(i, 0))
        self.rtl_lib.setToolTip("Biblioteca usada para abrir o RTL-SDR (vale na próxima vez que clicar em Ligar)")
        f.addRow(self.auto_tune)
        f.addRow("Calibração do S-meter:", self.smeter)
        f.addRow("Biblioteca do RTL-SDR:", self.rtl_lib)
        col1.addWidget(g)

        g = QGroupBox("Atualizações (somente www.pt2vhf.com)")
        f = QVBoxLayout(g)
        self.auto_update = QCheckBox("Verificar e instalar atualizações automaticamente")
        self.auto_update.setChecked(bool(cfg.get("auto_update", True)))
        self.auto_update.setToolTip("Ao detectar versão nova: baixa, confere tamanho e SHA-256 e instala quando "
                                    "o programa estiver livre (sem gravação ou varredura)")
        now = QPushButton("Verificar agora")
        f.addWidget(self.auto_update)
        f.addWidget(now)
        col1.addWidget(g)
        col1.addStretch(1)

        g = QGroupBox("Interface web · local e rede LAN")
        f = QVBoxLayout(g)
        self.web_on = QCheckBox("Habilitar interface web (abre junto com o programa)")
        self.web_on.setChecked(bool(cfg.get("web_enabled", False)))
        row = QHBoxLayout()
        self.web_lan = QCheckBox("Permitir outros dispositivos da rede local (LAN)")
        self.web_lan.setChecked(bool(cfg.get("web_allow_lan", False)))
        self.web_port = QSpinBox()
        self.web_port.setRange(1024, 65535)
        self.web_port.setValue(int(cfg.get("web_port", 8095)))
        row.addWidget(self.web_lan, 1)
        row.addWidget(QLabel("Porta TCP"))
        row.addWidget(self.web_port)
        btns = QHBoxLayout()
        b_open = QPushButton("Abrir interface web")
        b_copy = QPushButton("Copiar endereço")
        btns.addWidget(b_open)
        btns.addWidget(b_copy)
        self.web_status = QLabel("Interface web desativada")
        self.web_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.web_status.setObjectName("infoLabel")
        self.web_status.setWordWrap(True)
        info = QLabel("O navegador replica a sessão: display, waterfall, APRS e o áudio (que continua saindo "
                      "neste computador). Somente leitura: a sintonia é feita aqui. Na LAN o endereço leva uma "
                      "chave temporária. HTTP na rede local não é criptografado: nunca exponha a porta à Internet.")
        info.setWordWrap(True)
        info.setObjectName("hintLabel")
        for w in (self.web_on,):
            f.addWidget(w)
        f.addLayout(row)
        f.addLayout(btns)
        f.addWidget(self.web_status)
        f.addWidget(info)
        col2.addWidget(g)
        col2.addStretch(1)

        browse.clicked.connect(self._browse)
        self.call.editingFinished.connect(lambda: self.changed.emit("my_callsign", self.call.text().strip().upper()))
        self.locator.editingFinished.connect(lambda: self.changed.emit("my_locator", self.locator.text().strip()))
        self.rec_dir.editingFinished.connect(lambda: self.changed.emit("recordings_dir", self.rec_dir.text().strip()))
        self.level.currentTextChanged.connect(lambda v: self.changed.emit("ui_level", v))
        self.theme.currentTextChanged.connect(lambda v: self.changed.emit("lcd_theme", v))
        self.auto_tune.toggled.connect(lambda v: self.changed.emit("auto_tune", v))
        self.smeter.valueChanged.connect(lambda v: self.changed.emit("s_meter_cal", float(v)))
        self.auto_update.toggled.connect(lambda v: self.changed.emit("auto_update", v))
        self.rtl_lib.currentIndexChanged.connect(lambda _i: self.changed.emit("rtl_library", self.rtl_lib.currentData()))
        now.clicked.connect(self.checkUpdatesNow)
        for sig in (self.web_on.toggled, self.web_lan.toggled, self.web_port.valueChanged):
            sig.connect(lambda *_: self.webApply.emit())
        b_open.clicked.connect(self.webOpen)
        b_copy.clicked.connect(self.webCopy)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pasta de gravações", self.rec_dir.text())
        if d:
            self.rec_dir.setText(d)
            self.changed.emit("recordings_dir", d)
