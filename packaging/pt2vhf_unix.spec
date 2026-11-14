# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir for Linux and macOS; no Windows DLLs / .exe assets.

Commands:
  pyinstaller --noconfirm packaging/pt2vhf_unix.spec
  python packaging/package_unix.py --platform linux
  python packaging/package_unix.py --platform macos

The splash JPEG is mandatory, as it is in the Windows release spec.
"""
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files, collect_dynamic_libs, collect_submodules,
)

ROOT = Path.cwd().resolve()
APP = "pt2vhf-sdr"
BANNER = ROOT / "pt2vhf/assets/branding/welcome-banner.jpg"
if not BANNER.is_file():
    raise FileNotFoundError(
        "Missing original PT2VHF splash banner; add the user-supplied image "
        "via scripts/prepare_splash.py before building Linux/macOS packages."
    )

binaries = []
datas = [(str(BANNER), "pt2vhf/assets/branding")]
hiddenimports = ["pyqtgraph", "rtlsdr", "sounddevice"]
for pkg in (
    "pyqtgraph", "pyrtlsdrlib", "_sounddevice_data", "pyrnnoise",
    "faster_whisper", "ctranslate2", "tokenizers", "onnxruntime", "av",
    "huggingface_hub", "audiolab", "audiolab.av",
):
    try:
        binaries += collect_dynamic_libs(pkg)
        datas += collect_data_files(pkg)
        hiddenimports += collect_submodules(pkg)
    except (ImportError, ModuleNotFoundError, OSError, ValueError):
        pass

# RNNoise's optional audiolab backend requires Jinja2 templates when present.
try:
    from importlib.util import find_spec
    av_spec = find_spec("audiolab.av")
    if av_spec and av_spec.origin:
        templates = Path(av_spec.origin).parent / "templates"
        if templates.is_dir():
            datas.append((str(templates), "audiolab/av/templates"))
except (ImportError, ModuleNotFoundError, ValueError):
    pass

EXCLUDES = [
    "tkinter", "pytest", "IPython",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuick3D",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
    "PySide6.QtBluetooth", "PySide6.QtNetwork", "PySide6.QtSql",
    "PySide6.QtDesigner", "PySide6.QtLocation", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtTest",
    "PySide6.QtVirtualKeyboard", "PySide6.QtSpatialAudio", "PySide6.QtGraphs",
]

a = Analysis(
    [str(ROOT / "run_pt2vhf.py")], pathex=[str(ROOT)],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    excludes=EXCLUDES,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name=APP, console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=APP)

if sys.platform == "darwin":
    from pt2vhf import __version__
    icon_path = ROOT / "packaging/pt2vhf.icns"
    app = BUNDLE(
        coll,
        name="PT2VHF SDR Tool.app",
        icon=str(icon_path) if icon_path.is_file() else None,
        bundle_identifier="com.pt2vhf.sdrtool",
        info_plist={
            "CFBundleName": "PT2VHF SDR Tool",
            "CFBundleDisplayName": "PT2VHF SDR Tool",
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSMicrophoneUsageDescription": (
                "PT2VHF SDR Tool receives and processes audio from connected radio devices."
            ),
        },
    )
