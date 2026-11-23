# -*- mode: python ; coding: utf-8 -*-
# Build (Windows):  pyinstaller --noconfirm pt2vhf.spec
#   dist/PT2VHF-SDR-Tool/PT2VHF-SDR-Tool.exe   -> pasta usada pelo instalador (Inno Setup)
#   dist/PT2VHF-SDR-Tool-Portable.exe          -> versão portátil (um único .exe)
import os
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

binaries, datas = [], []
hiddenimports = collect_submodules("pyqtgraph") + ["rtlsdr", "sounddevice"]
for pkg in ("pyrtlsdrlib", "_sounddevice_data", "pyrnnoise", "faster_whisper",
            "ctranslate2", "tokenizers", "onnxruntime", "huggingface_hub", "av",
            "audiolab", "audiolab.av"):
    try:
        binaries += collect_dynamic_libs(pkg)
        datas += collect_data_files(pkg)
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

import os
from importlib.util import find_spec
# audiolab.av usa Jinja2.PackageLoader("audiolab.av", "templates") no pipeline
# pyrnnoise. PyInstaller nao encontra templates sem inclusao explicita.
av_spec = find_spec("audiolab.av")
if av_spec and av_spec.origin:
    av_templates = os.path.join(os.path.dirname(av_spec.origin), "templates")
    if os.path.isdir(av_templates):
        datas.append((av_templates, "audiolab/av/templates"))
    else:
        raise RuntimeError("Dependencia audiolab.av sem pasta templates: verifique o wheel")
datas += [("scripts/apply-update.ps1", "scripts")]
# Bundled into both the Windows Setup (onedir) and Portable (onefile).
# The same PyInstaller spec works for Linux/macOS if these builds are enabled.
banner_path = os.path.join("pt2vhf", "assets", "branding", "welcome-banner.jpg")
if not os.path.isfile(banner_path):
    # The approved v1.0.2 RSP experiment keeps the existing text-only
    # splash when the original 7-project JPG is unavailable. This is an
    # explicit, release-scoped choice, not a silent placeholder image.
    allow_text = os.environ.get("PT2VHF_RELEASE_TEXT_SPLASH") == "1"
    if os.environ.get("PT2VHF_QA_ALLOW_MISSING_BANNER") != "1" and not allow_text:
        raise FileNotFoundError(
            "PT2VHF splash banner missing. Run scripts/prepare_splash.py with "
            "the supplied 7-project PT2VHF image before packaging.")
else:
    datas.append((banner_path, "pt2vhf/assets/branding"))
for f in ("drivers/wdi-simple.exe", "drivers/libwdi-COPYING-LGPL.txt"):
    if os.path.isfile(f):
        datas.append((f, "drivers"))
# Decodificadores RS41 (fsk_demod LGPL-2.1, rs41mod GPL-3.0) + licenças e fonte
# correspondente, gerados por packaging/build_sonde_decoders.sh. No Windows o
# pacote é obrigatório: sem eles a aba Sondas > Recepção RF não funciona.
sonde_dir = os.path.join("packaging", "sonde_decoders")
if os.path.isdir(sonde_dir):
    for root, _dirs, files in os.walk(sonde_dir):
        rel = os.path.relpath(root, "packaging")
        for f in files:
            datas.append((os.path.join(root, f), rel))
elif os.name == "nt" and os.environ.get("PT2VHF_ALLOW_MISSING_SONDE") != "1":
    raise FileNotFoundError(
        "packaging/sonde_decoders ausente. Rode packaging/build_sonde_decoders.sh "
        "windows antes do PyInstaller (fsk_demod/rs41mod embarcados).")
blog_dir = os.path.join("packaging", "rtlsdr_blog")
if os.path.isdir(blog_dir):
    for f in os.listdir(blog_dir):
        p = os.path.join(blog_dir, f)
        (binaries if f.lower().endswith(".dll") else datas).append((p, "rtlsdr_blog"))

EXCLUDES = ["tkinter", "matplotlib", "IPython", "pytest",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
            "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml",
            "PySide6.QtQuick3D", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtBluetooth",
            "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtDesigner", "PySide6.QtLocation",
            "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtTest",
            "PySide6.QtVirtualKeyboard", "PySide6.QtSpatialAudio", "PySide6.QtGraphs"]

a = Analysis(["run_pt2vhf.py"], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=EXCLUDES)
pyz = PYZ(a.pure)

# pasta (instalador)
exe_dir = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PT2VHF-SDR-Tool",
              console=False, icon="packaging/pt2vhf.ico", version="packaging/version_info.txt")
coll = COLLECT(exe_dir, a.binaries, a.datas, name="PT2VHF-SDR-Tool")

# portátil (arquivo único)
exe_one = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="PT2VHF-SDR-Tool-Portable",
              console=False, icon="packaging/pt2vhf.ico", version="packaging/version_info.txt",
              runtime_tmpdir=None)
