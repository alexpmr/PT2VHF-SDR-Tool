"""Medição leve de CPU e memória do processo PT2VHF SDR Tool.

Sem dependências nativas adicionais, threads de coleta ou I/O de rede.
A CPU corresponde à fração da capacidade total dos CPUs lógicos, como
o indicador de processo no Gerenciador de Tarefas do Windows.
"""
from __future__ import annotations

import ctypes
import os
import sys
import time


def process_rss_bytes() -> int | None:
    """Memória física residente do processo (RSS/working set), em bytes."""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes

            size_t = ctypes.c_size_t

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", size_t),
                    ("WorkingSetSize", size_t),
                    ("QuotaPeakPagedPoolUsage", size_t),
                    ("QuotaPagedPoolUsage", size_t),
                    ("QuotaPeakNonPagedPoolUsage", size_t),
                    ("QuotaNonPagedPoolUsage", size_t),
                    ("PagefileUsage", size_t),
                    ("PeakPagefileUsage", size_t),
                ]

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            data = PROCESS_MEMORY_COUNTERS()
            data.cb = ctypes.sizeof(data)
            if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(data), data.cb):
                return int(data.WorkingSetSize)
            return None
        except (OSError, AttributeError, ValueError):
            return None
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/self/statm", "r", encoding="ascii") as f:
                pages = int(f.read().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE")
        except (OSError, IndexError, ValueError):
            return None
    if sys.platform == "darwin":
        # Fallback portability: ru_maxrss on Darwin is bytes and describes
        # the peak RSS. Avoiding psutil/extra dylibs keeps packaging stable.
        try:
            import resource
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except (OSError, ImportError, AttributeError):
            return None
    return None


class ProcessResourceSampler:
    """Amos­tragem não bloqueante da CPU e RSS deste aplicativo."""

    def __init__(self, *, clock=time.monotonic, cpu_clock=time.process_time,
                 cpu_count=None, rss_reader=process_rss_bytes):
        self._clock = clock
        self._cpu_clock = cpu_clock
        self._rss = rss_reader
        self._cores = max(1, int(cpu_count or os.cpu_count() or 1))
        self._last_wall = self._clock()
        self._last_cpu = self._cpu_clock()

    def sample(self) -> tuple[float | None, int | None]:
        now_wall, now_cpu = self._clock(), self._cpu_clock()
        delta_wall = now_wall - self._last_wall
        delta_cpu = now_cpu - self._last_cpu
        self._last_wall, self._last_cpu = now_wall, now_cpu
        # On first sample / zero interval, do not show invented 0% CPU.
        percent = None if delta_wall <= 0 else max(
            0.0, min(100.0, 100.0 * delta_cpu / (delta_wall * self._cores)))
        return percent, self._rss()
