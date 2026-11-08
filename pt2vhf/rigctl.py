"""Controle CAT seguro do SDR via daemon Hamlib rigctld (TCP, padrão 4532).

Comandos não incluem PTT/transmissão. Requer servidor rigctld externo ativo.
"""
from __future__ import annotations

import math
import socket


class RigCtlError(RuntimeError):
    pass


SDR_TO_HAMLIB = {"NFM": "FM", "WFM": "WFM", "AM": "AM", "USB": "USB",
                 "LSB": "LSB", "CW": "CW", "DSB": "DSB"}
HAMLIB_TO_SDR = {"FM": "NFM", "FMN": "NFM", "WFM": "WFM",
                 "AM": "AM", "USB": "USB", "LSB": "LSB",
                 "CW": "CW", "CWR": "CW", "DSB": "DSB"}


class RigCtlClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 4532, timeout: float = 1.5):
        if not host.strip():
            raise ValueError("Host CAT vazio")
        if not 1 <= int(port) <= 65535:
            raise ValueError("Porta CAT inválida")
        self.host, self.port, self.timeout = host.strip(), int(port), float(timeout)

    def _cmd(self, line: str) -> list[str]:
        if "\n" in line or "\r" in line or len(line) > 160:
            raise ValueError("Comando CAT inválido")
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            sock.sendall((line + "\n").encode("ascii", errors="strict"))
            f = sock.makefile("r", encoding="ascii", errors="replace", newline="\n")
            rows = []
            for _ in range(5):
                try:
                    value = f.readline()
                except TimeoutError:
                    break
                if not value:
                    break
                value = value.strip()
                if value:
                    rows.append(value)
                if value.startswith("RPRT "):
                    break
                if line == "f" and rows:
                    break
                if line == "m" and len(rows) >= 2:
                    break
            if any(x.startswith("RPRT -") for x in rows):
                raise RigCtlError("Hamlib: " + ", ".join(rows))
            if not rows:
                raise RigCtlError("Sem resposta do rigctld")
            return rows

    def read(self) -> tuple[float, str]:
        f = self._cmd("f")[0]
        try:
            hz = float(f)
        except ValueError as exc:
            raise RigCtlError("Resposta de frequência inválida: " + f) from exc
        if not (math.isfinite(hz) and 1_000 <= hz <= 10e9):
            raise RigCtlError("Frequência CAT fora do intervalo")
        rows = self._cmd("m")
        mode = rows[0].upper()
        return hz, HAMLIB_TO_SDR.get(mode, "")

    def write(self, hz: float, sdr_mode: str) -> None:
        mode = SDR_TO_HAMLIB.get(sdr_mode)
        if mode is None:
            raise ValueError(f"Modo {sdr_mode} não suportado pelo rigctld")
        if not math.isfinite(hz) or not 1_000 <= hz <= 10e9:
            raise ValueError("Frequência CAT inválida")
        self._cmd(f"F {int(round(hz))}")
        self._cmd(f"M {mode} 0")
