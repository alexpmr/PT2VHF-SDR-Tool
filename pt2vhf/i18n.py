"""Menu de idiomas PT2VHF com bandeiras vetoriais e traduções parciais declaradas.

Traduções operam somente em texto de apresentação. Identificadores internos de
modos, valores de configuração e nomes dos grupos usados na lógica permanecem
em português. Qualquer termo ausente mantém o texto original, sem tradutor online.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QTabWidget

LANGUAGES = (
    ("pt", "Português (Brasil)", "BR"),
    ("en", "English", "GB"),
    ("es", "Español", "ES"),
    ("fr", "Français", "FR"),
    ("de", "Deutsch", "DE"),
    ("it", "Italiano", "IT"),
    ("zh", "简体中文", "CN"),
)
LANG_INDEX = {code: i for i, (code, *_rest) in enumerate(LANGUAGES)}
# Na ordem EN, ES, FR, DE, IT, ZH
WORDS = {
    "Receptor": ("Receiver", "Receptor", "Récepteur", "Empfänger", "Ricevitore", "接收机"),
    "Memórias / Varredura": ("Memories / Scan", "Memorias / Barrido", "Mémoires / Balayage", "Speicher / Suchlauf", "Memorie / Scansione", "存储 / 扫描"),
    "Scanner": ("Scanner", "Escáner", "Scanner", "Scanner", "Scanner", "扫描器"),
    "Decodificadores": ("Decoders", "Decodificadores", "Décodeurs", "Decoder", "Decodificatori", "解码器"),
    "Decodificação": ("Decoding", "Decodificación", "Décodage", "Dekodierung", "Decodifica", "解码"),
    "Ferramentas": ("Tools", "Herramientas", "Outils", "Werkzeuge", "Strumenti", "工具"),
    "Transcrição": ("Transcription", "Transcripción", "Transcription", "Transkription", "Trascrizione", "转录"),
    "Sondas Meteorológicas": ("Weather Radiosondes", "Radiosondas meteorológicas", "Radiosondes météorologiques", "Wettersonden", "Radiosonde meteorologiche", "气象探空仪"),
    "Recepção RF · RS41": ("RF reception · RS41", "Recepción RF · RS41", "Réception RF · RS41", "RF-Empfang · RS41", "Ricezione RF · RS41", "射频接收 · RS41"),
    "Telemetria externa": ("External telemetry", "Telemetría externa", "Télémétrie externe", "Externe Telemetrie", "Telemetria esterna", "外部遥测"),
    "APRS / DTMF / CTCSS": ("APRS / DTMF / CTCSS", "APRS / DTMF / CTCSS", "APRS / DTMF / CTCSS", "APRS / DTMF / CTCSS", "APRS / DTMF / CTCSS", "APRS / DTMF / CTCSS"),
    "ADS-B": ("ADS-B", "ADS-B", "ADS-B", "ADS-B", "ADS-B", "ADS-B"),
    "AIS": ("AIS", "AIS", "AIS", "AIS", "AIS", "AIS"),
    "Receptores extras": ("Extra receivers", "Receptores adicionales", "Récepteurs supplémentaires", "Zusätzliche Empfänger", "Ricevitori aggiuntivi", "附加接收机"),
    "Satélites": ("Satellites", "Satélites", "Satellites", "Satelliten", "Satelliti", "卫星"),
    "Configurações": ("Settings", "Configuración", "Paramètres", "Einstellungen", "Impostazioni", "设置"),
    "Display": ("Display", "Pantalla", "Affichage", "Anzeige", "Schermo", "显示"),
    "Modo / Filtro": ("Mode / Filter", "Modo / Filtro", "Mode / Filtre", "Modus / Filter", "Modo / Filtro", "模式 / 滤波"),
    "Geral · Web · Atualizações": ("General · Web · Updates", "General · Web · Actualizaciones", "Général · Web · Mises à jour", "Allgemein · Web · Updates", "Generale · Web · Aggiornamenti", "常规 · 网页 · 更新"),
    "CAT · Hamlib": ("CAT · Hamlib", "CAT · Hamlib", "CAT · Hamlib", "CAT · Hamlib", "CAT · Hamlib", "CAT · Hamlib"),
    "ADS-B / AIS / Sondas": ("ADS-B / AIS / Radiosondes", "ADS-B / AIS / Sondas", "ADS-B / AIS / Sondes", "ADS-B / AIS / Sonden", "ADS-B / AIS / Sonde", "ADS-B / AIS / 探空仪"),
    "APRS iGate RX": ("APRS RX-only iGate", "APRS iGate solo RX", "Passerelle APRS RX", "APRS Empfangs-iGate", "APRS iGate solo RX", "APRS 只接收网关"),
    "RS41 · IQ ao vivo": ("RS41 · Live IQ", "RS41 · IQ en vivo", "RS41 · IQ en direct", "RS41 · Live IQ", "RS41 · IQ in diretta", "RS41 · 实时 IQ"),
    "Ocupação 24 h": ("24-hour activity", "Actividad 24 h", "Activité 24 h", "24-Stunden-Aktivität", "Attività 24 h", "24小时活动"),
    "Legendas ao vivo": ("Live captions", "Subtítulos en vivo", "Sous-titres en direct", "Live-Untertitel", "Sottotitoli live", "实时字幕"),
    "Verificar atualizações": ("Check updates", "Buscar actualizaciones", "Vérifier les mises à jour", "Nach Updates suchen", "Controlla aggiornamenti", "检查更新"),
    "▶  Ligar": ("▶  Power on", "▶  Encender", "▶  Allumer", "▶  Einschalten", "▶  Accendi", "▶  开机"),
    "■  Desligar": ("■  Power off", "■  Apagar", "■  Éteindre", "■  Ausschalten", "■  Spegni", "■  关闭"),
    "Tela cheia": ("Full screen", "Pantalla completa", "Plein écran", "Vollbild", "Schermo intero", "全屏"),
    "Receptor parado": ("Receiver stopped", "Receptor detenido", "Récepteur arrêté", "Empfänger gestoppt", "Ricevitore fermo", "接收机已停止"),
    "Áudio: OK": ("Audio: OK", "Audio: OK", "Audio : OK", "Audio: OK", "Audio: OK", "音频：正常"),
    "Áudio indisponível": ("Audio unavailable", "Audio no disponible", "Audio indisponible", "Audio nicht verfügbar", "Audio non disponibile", "音频不可用"),
    "Indicativo:": ("Callsign:", "Indicativo:", "Indicatif :", "Rufzeichen:", "Nominativo:", "呼号："),
    "Locator (grid):": ("Grid locator:", "Localizador:", "Locator :", "Grid-Locator:", "Locator:", "网格定位："),
    "Pasta de gravações:": ("Recordings folder:", "Carpeta de grabaciones:", "Dossier des enregistrements :", "Aufnahmeordner:", "Cartella registrazioni:", "录音目录："),
    "Nível da interface:": ("Interface level:", "Nivel de interfaz:", "Niveau d'interface :", "Oberflächenstufe:", "Livello interfaccia:", "界面等级："),
    "Entrar no modo apresentação": ("Enter presentation mode", "Activar presentación", "Mode présentation", "Präsentationsmodus", "Modalità presentazione", "进入演示模式"),
    "Verificar agora": ("Check now", "Comprobar ahora", "Vérifier maintenant", "Jetzt prüfen", "Controlla ora", "立即检查"),
    "Abrir interface web": ("Open web interface", "Abrir interfaz web", "Ouvrir l'interface web", "Weboberfläche öffnen", "Apri interfaccia web", "打开网页界面"),
    "Copiar endereço": ("Copy address", "Copiar dirección", "Copier l'adresse", "Adresse kopieren", "Copia indirizzo", "复制地址"),
    "Interface web desativada": ("Web interface disabled", "Interfaz web desactivada", "Interface web désactivée", "Weboberfläche deaktiviert", "Interfaccia web disattivata", "网页界面已禁用"),
    "Atualizar agora": ("Refresh now", "Actualizar ahora", "Actualiser", "Jetzt aktualisieren", "Aggiorna ora", "立即更新"),
    "Exportar CSV": ("Export CSV", "Exportar CSV", "Exporter CSV", "CSV exportieren", "Esporta CSV", "导出 CSV"),
    "Ligar": ("Start", "Iniciar", "Démarrer", "Starten", "Avvia", "启动"),
    "Parar": ("Stop", "Parar", "Arrêter", "Stoppen", "Ferma", "停止"),
    "Salvar": ("Save", "Guardar", "Enregistrer", "Speichern", "Salva", "保存"),
    "Limpar": ("Clear", "Limpiar", "Effacer", "Leeren", "Pulisci", "清除"),
    "Editar": ("Edit", "Editar", "Modifier", "Bearbeiten", "Modifica", "编辑"),
    "Excluir": ("Delete", "Eliminar", "Supprimer", "Löschen", "Elimina", "删除"),
    "&Arquivo": ("&File", "&Archivo", "&Fichier", "&Datei", "&File", "文件(&F)"),
    "&Exibir": ("&View", "&Ver", "A&ffichage", "&Ansicht", "&Visualizza", "视图(&V)"),
    "A&juda": ("&Help", "A&yuda", "A&ide", "&Hilfe", "A&iuto", "帮助(&H)"),
    "Sobre": ("About", "Acerca de", "À propos", "Über", "Informazioni", "关于"),
    "Sair": ("Exit", "Salir", "Quitter", "Beenden", "Esci", "退出"),
    "Atalhos de teclado": ("Keyboard shortcuts", "Atajos de teclado", "Raccourcis clavier", "Tastenkürzel", "Scorciatoie", "键盘快捷键"),
}


def translate(text: str, code: str) -> str:
    if code not in LANG_INDEX:
        code = "pt"
    if code == "pt":
        return text
    item = WORDS.get(text)
    return item[LANG_INDEX[code] - 1] if item else text


def flag_icon(country: str) -> QIcon:
    """Desenha bandeiras pequenas; não requer fonte de emoji nem recursos externos."""
    pix = QPixmap(28, 18)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, False)
    def fill(color, x=0, y=0, w=28, h=18):
        painter.fillRect(x, y, w, h, QColor(color))
    if country in ("FR", "IT"):
        a, b, c = ("#0055a4", "#ffffff", "#ef4135") if country == "FR" else ("#009246", "#ffffff", "#ce2b37")
        fill(a, 0, 0, 9, 18); fill(b, 9, 0, 10, 18); fill(c, 19, 0, 9, 18)
    elif country == "DE":
        fill("#000000", 0, 0, 28, 6); fill("#dd0000", 0, 6, 28, 6); fill("#ffce00", 0, 12, 28, 6)
    elif country == "ES":
        fill("#aa151b"); fill("#f1bf00", 0, 4, 28, 10)
    elif country == "CN":
        fill("#de2910")
        painter.setPen(QColor("#ffde00")); painter.drawText(3, 11, "★")
    elif country == "BR":
        fill("#009c3b")
        painter.setBrush(QColor("#ffdf00")); painter.setPen(Qt.NoPen)
        painter.drawPolygon(QPolygon([QPoint(14, 2), QPoint(26, 9), QPoint(14, 16), QPoint(2, 9)]))
        painter.setBrush(QColor("#002776")); painter.drawEllipse(9, 4, 10, 10)
    elif country == "GB":
        fill("#012169")
        painter.setPen(QColor("#ffffff")); painter.setPen(QColor("#ffffff"))
        painter.drawLine(0, 0, 28, 18); painter.drawLine(0, 18, 28, 0)
        fill("#ffffff", 10, 0, 8, 18); fill("#ffffff", 0, 6, 28, 6)
        fill("#c8102e", 12, 0, 4, 18); fill("#c8102e", 0, 8, 28, 3)
    else:
        fill("#999999")
    painter.end()
    return QIcon(pix)


def apply_language(root, code: str) -> None:
    """Traduz catálogo nos controles existentes, com retorno confiável a PT-BR."""
    for widget in (root.findChildren(QLabel) + root.findChildren(QAbstractButton) +
                   root.findChildren(QGroupBox)):
        if isinstance(widget, QGroupBox):
            getter, setter, key = widget.title, widget.setTitle, "_original_group_title"
        elif isinstance(widget, QLabel):
            getter, setter, key = widget.text, widget.setText, "_original_label"
        elif isinstance(widget, QAbstractButton):
            getter, setter, key = widget.text, widget.setText, "_original_button"
        else:
            continue
        original = widget.property(key)
        if original is None:
            original = getter()
            widget.setProperty(key, original)
        if original in WORDS:
            setter(translate(original, code))
    for tabs in root.findChildren(QTabWidget):
        for i in range(tabs.count()):
            page = tabs.widget(i)
            orig = page.property("_original_tab_title")
            if orig is None:
                orig = tabs.tabText(i)
                page.setProperty("_original_tab_title", orig)
            tabs.setTabText(i, translate(orig, code))
    for act in root.findChildren(QAction):
        orig = act.property("_original_action")
        if orig is None:
            orig = act.text()
            act.setProperty("_original_action", orig)
        if orig in WORDS:
            act.setText(translate(orig, code))
