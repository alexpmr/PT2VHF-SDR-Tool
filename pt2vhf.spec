# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller pt2vhf.spec   ->  dist/PT2VHF-SDR-Tool/PT2VHF-SDR-Tool.exe
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

binaries = []
datas = []
hiddenimports = collect_submodules("pyqtgraph") + ["rtlsdr", "sounddevice"]
for pkg in ("pyrtlsdrlib", "_sounddevice_data"):
    try:
        binaries += collect_dynamic_libs(pkg)
        datas += collect_data_files(pkg)
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

a = Analysis(
    ["run_pt2vhf.py"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PT2VHF-SDR-Tool",
          console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, name="PT2VHF-SDR-Tool")
