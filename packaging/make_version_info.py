"""Gera packaging/version_info.txt (metadados do .exe) a partir de pt2vhf/__init__.py."""
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
v = re.search(r'__version__ = "([\d.]+)"', (root / "pt2vhf/__init__.py").read_text()).group(1)
t = tuple(int(x) for x in v.split(".")) + (0,)
(root / "packaging/version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0),
  kids=[StringFileInfo([StringTable('041604b0', [
    StringStruct('CompanyName', 'PT2VHF'),
    StringStruct('FileDescription', 'PT2VHF SDR Tool'),
    StringStruct('FileVersion', '{v}'),
    StringStruct('InternalName', 'PT2VHF-SDR-Tool'),
    StringStruct('LegalCopyright', 'PT2VHF'),
    StringStruct('OriginalFilename', 'PT2VHF-SDR-Tool.exe'),
    StringStruct('ProductName', 'PT2VHF SDR Tool'),
    StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])]
)
""", encoding="utf-8")
print(v)
