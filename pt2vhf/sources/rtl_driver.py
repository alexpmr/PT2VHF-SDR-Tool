"""RTL-SDR plug and play: diagnóstico do driver e preparação automática do sistema.

Windows: consulta o PnP (driver associado à interface 0 do RTL2832U) e instala WinUSB com o
`wdi-simple.exe` da libwdi (a mesma base do Zadig), embarcado no pacote, com um único UAC.
Adaptado do PT2VHF Sat Tool (mesmo comportamento nos programas PT2VHF).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

RTL_IDS = (("0BDA", "2838"), ("0BDA", "2832"))
GOOD_SERVICES = {"winusb", "libusbk", "libusb0", "libusb0_x64"}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class UsbInterface:
    instance_id: str
    pid: str
    mi: Optional[int]          # None em dispositivo não composto
    service: str               # driver associado (WinUSB, RTL2832UUSB, vazio = sem driver)
    status: str = ""
    name: str = ""

    @property
    def radio_interface(self) -> bool:
        return self.mi in (None, 0)

    @property
    def ready(self) -> bool:
        return self.service.lower() in GOOD_SERVICES


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def wdi_simple_path() -> Optional[Path]:
    for candidate in (_bundle_root() / "drivers" / "wdi-simple.exe",
                      Path(sys.executable).resolve().parent / "drivers" / "wdi-simple.exe"):
        if candidate.is_file():
            return candidate
    return None


def parse_pnp_json(text: str) -> list[UsbInterface]:
    """Converte a saída JSON do PowerShell (objeto ou lista) em interfaces RTL-SDR."""
    text = (text or "").strip()
    if not text:
        return []
    data = json.loads(text)
    rows = data if isinstance(data, list) else [data]
    out = []
    for row in rows:
        iid = str(row.get("InstanceId") or "").upper()
        pid = next((p for v, p in RTL_IDS if f"VID_{v}&PID_{p}" in iid), None)
        if not pid:
            continue
        mi = None
        if "&MI_" in iid:
            try:
                mi = int(iid.split("&MI_", 1)[1][:2], 16)
            except ValueError:
                mi = None
        out.append(UsbInterface(iid, pid, mi, str(row.get("Service") or ""), str(row.get("Status") or ""),
                                str(row.get("FriendlyName") or "")))
    # Em dispositivos compostos o nó pai (sem MI) usa usbccgp: só interessam as interfaces.
    if any(i.mi is not None for i in out):
        out = [i for i in out if i.mi is not None]
    return out


def windows_interfaces() -> list[UsbInterface]:
    if sys.platform != "win32":
        return []
    script = ("$ErrorActionPreference='SilentlyContinue';"
              "Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_0BDA&PID_283[28]' } | "
              "Select-Object InstanceId,Service,Status,FriendlyName | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
        return parse_pnp_json(result.stdout)
    except Exception:
        return []


def windows_needs_winusb(interfaces: list[UsbInterface]) -> list[UsbInterface]:
    return [i for i in interfaces if i.radio_interface and not i.ready]


def wdi_arguments(pid: str, workdir: Path) -> list[str]:
    """Somente WinUSB (-t 0) e somente a interface 0 (-i 0): a interface 1 nunca é tocada."""
    return ["-n", "RTL2832U (PT2VHF SDR Tool)", "-m", "Realtek", "-v", "0x0BDA", "-p", f"0x{pid}",
            "-i", "0", "-t", "0", "-f", f"rtlsdr_{pid.lower()}_pt2vhf.inf", "-d", str(workdir),
            "--stealth-cert", "-o", "60000"]


def install_winusb(pid: str) -> tuple[bool, str]:
    """Executa o wdi-simple elevado (um UAC) e aguarda. Retorna (sucesso, mensagem)."""
    exe = wdi_simple_path()
    if exe is None:
        return False, "Instalador de driver (wdi-simple.exe) não incluído neste pacote."
    import ctypes
    from ctypes import wintypes
    workdir = Path(os.environ.get("TEMP", ".")) / "pt2vhf_rtlsdr_driver"
    workdir.mkdir(parents=True, exist_ok=True)
    params = subprocess.list2cmdline(wdi_arguments(pid, workdir))

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb, info.lpFile, info.lpParameters = "runas", str(exe), params
    info.lpDirectory, info.nShow = str(exe.parent), 0
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return False, "Instalação cancelada ou permissão de administrador negada."
    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, 180_000)
    code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    if code.value != 0:
        return False, f"O instalador do driver terminou com código {int(code.value)}."
    return True, "Driver WinUSB instalado na interface 0 do RTL-SDR."


# ----------------------------------------------------------------------------- Diagnóstico
def needs_preparation() -> tuple[bool, str, Optional[str]]:
    """(precisa preparar?, motivo legível, pid alvo no Windows)."""
    if sys.platform == "win32":
        pending = windows_needs_winusb(windows_interfaces())
        if pending:
            i = pending[0]
            return True, f"Interface 0 do RTL-SDR usa o driver '{i.service or 'nenhum'}' (precisa WinUSB).", i.pid
    return False, "", None


def prepare() -> tuple[bool, str]:
    need, _reason, pid = needs_preparation()
    if not need:
        return True, "Nada a preparar: o RTL-SDR já usa o driver WinUSB."
    return install_winusb(pid or "2838")


def diagnose() -> str:
    """Relatório para a tela e o log: biblioteca, USB, driver e abertura do dispositivo."""
    from .rtlsdr_source import library_info, list_devices, tuning_range
    lines = [f"Sistema: {sys.platform}"]
    info = library_info()
    if info.get("error"):
        lines.append(f"Biblioteca librtlsdr: NÃO carregou ({info['error']})")
    else:
        lines.append("Biblioteca librtlsdr: carregada" + (" — driver RTL-SDR Blog (suporte ao V4)" if info.get("blog")
                                                          else " — versão padrão (osmocom)"))
    devices = list_devices()
    lines.append(f"Dispositivos: {len(devices)}")
    lines += [f"  {d}" for d in devices]
    if sys.platform == "win32":
        ifaces = windows_interfaces()
        lines.append(f"USB (PnP do Windows): {len(ifaces)} interface(s) RTL2832U")
        for i in ifaces:
            mi = "—" if i.mi is None else f"{i.mi}"
            lines.append(f"  PID {i.pid} · interface {mi} · driver {i.service or 'nenhum'} · {i.status}"
                         + ("" if i.ready or not i.radio_interface else "  ← precisa WinUSB"))
        lines.append("Instalador de driver embarcado: " + ("sim" if wdi_simple_path() else "não"))
    if devices:
        try:
            from rtlsdr import RtlSdr
            radio = RtlSdr(0)
            names = {1: "E4000", 2: "FC0012", 3: "FC0013", 4: "FC2580", 5: "R820T", 6: "R828D"}
            tuner = names.get(int(radio.get_tuner_type()), "?")
            radio.close()
            lo, hi = tuning_range(tuner, info.get("blog", False), 0, devices[0])
            lines.append(f"Abertura do dispositivo #0: OK (sintonizador {tuner}, {lo / 1e6:g}–{hi / 1e6:g} MHz)")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"Abertura do dispositivo #0: FALHOU — {exc}")
            lines.append("Recomendação: feche outros programas SDR, use Preparar RTL-SDR e reconecte o dongle.")
    return "\n".join(lines)
