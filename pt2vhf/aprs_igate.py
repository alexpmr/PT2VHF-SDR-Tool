"""APRS-IS iGate RF -> IS (somente RX de rádio; sem transmissão RF).

O modo somente RX usa qAO conforme a especificação APRS-IS, nunca qAR.
Configuração desativada por padrão, exige indicativo válido e passcode verificado
fornecido pelo operador. Não usa um passcode embutido nem converte tráfego IS->RF.
"""
from __future__ import annotations

import logging
import queue
import re
import socket
import threading
import time

log = logging.getLogger(__name__)
CALLSIGN_RE = re.compile(r"^[A-Z0-9]{3,7}(?:-(?:[0-9]|1[0-5]))?$")
BLOCKED_PATH = {"TCPIP", "TCPXX", "NOGATE", "RFONLY", "IGATE", "GATE"}
SEEN_WINDOW = 45.0


def clean_call(value: str) -> str:
    call = value.strip().upper()
    if not CALLSIGN_RE.fullmatch(call):
        raise ValueError("Indicativo APRS-IS inválido (com SSID -0 a -15 opcional)")
    return call


def gate_line(raw: str, gate_call: str) -> str | None:
    """Valida e transforma quadro TNC2 RF num pacote APRS-IS qAO.

    Pacotes já passados por iGate, tráfego de Internet, de terceiros
    e cabeçalhos malformados são descartados; limite de 512 bytes/linha.
    """
    gate_call = clean_call(gate_call)
    if not isinstance(raw, str) or any(c in raw for c in "\r\n\x00"):
        return None
    header, sep, payload = raw.partition(":")
    if sep != ":" or not payload or payload.startswith("}"):
        return None
    source, arrow, rest = header.partition(">")
    if not arrow:
        return None
    try:
        clean_call(source)
    except ValueError:
        return None
    fields = rest.split(",")
    if not fields or not re.fullmatch(r"[A-Z0-9]{1,9}", fields[0].upper()):
        return None
    path = fields[1:]
    for part in path:
        upper = part.upper().rstrip("*")
        if (upper in BLOCKED_PATH or upper.startswith("QA")
                or not re.fullmatch(r"[A-Z0-9-]{1,10}", upper)):
            return None
    # qAO é obrigatório para iGate RX-only, pois não roteia mensagens de IS para RF.
    gated = f"{header},qAO,{gate_call}:{payload}"
    try:
        encoded = gated.encode("latin-1", errors="strict")
    except UnicodeError:
        return None
    if len(encoded) + 2 > 512:
        return None
    return gated


class ReceiveOnlyIGate:
    """Envia RF APRS validado para APRS-IS com fila limitada, sem bloquear o DSP."""

    def __init__(self, callsign: str, passcode: str, host="rotate.aprs2.net", port=14580,
                 software_version="0.9.0", on_status=None):
        self.callsign = clean_call(callsign)
        self.passcode = str(passcode).strip()
        if not re.fullmatch(r"\d{1,5}", self.passcode):
            raise ValueError("Informe um passcode APRS-IS válido de 1 a 5 dígitos")
        self.host, self.port = str(host).strip(), int(port)
        if not self.host or not 1 <= self.port <= 65535:
            raise ValueError("Servidor APRS-IS inválido")
        self.version = re.sub(r"[^0-9A-Za-z._-]", "", software_version)[:25]
        self.on_status = on_status
        self._queue: queue.Queue = queue.Queue(maxsize=256)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._seen: dict[str, float] = {}
        self.sent = 0
        self.dropped = 0
        self.verified = False
        self._lock = threading.Lock()

    def _status(self, text):
        if self.on_status:
            self.on_status(text)

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pt2vhf-igate", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        t = self._thread
        if t is not None and t.is_alive() and threading.current_thread() is not t:
            t.join(timeout=3)
        self._thread = None
        self.verified = False

    def submit(self, raw: str) -> bool:
        """Pode ser chamada no Qt tick; retorna sem aguardar socket."""
        converted = gate_line(raw, self.callsign)
        if converted is None:
            self.dropped += 1
            return False
        now = time.monotonic()
        # Evita duplicatas de retransmissões RF, sem bloquear a thread de interface.
        with self._lock:
            self._seen = {k: t for k, t in self._seen.items() if now - t < SEEN_WINDOW}
            if converted in self._seen:
                self.dropped += 1
                return False
            self._seen[converted] = now
        try:
            self._queue.put_nowait(converted)
        except queue.Full:
            self.dropped += 1
            return False
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=7.0) as sock:
                    sock.settimeout(1.5)
                    login = f"user {self.callsign} pass {self.passcode} vers PT2VHF-SDR {self.version}\r\n"
                    sock.sendall(login.encode("ascii"))
                    # Resposta textual do servidor: esperar confirmação explícita.
                    with sock.makefile("rb") as stream:
                        deadline = time.monotonic() + 12
                        verified = False
                        while time.monotonic() < deadline and not self._stop.is_set():
                            try:
                                raw = stream.readline(1024)
                            except (socket.timeout, TimeoutError, OSError):
                                continue
                            if not raw:
                                break
                            line = raw.decode("ascii", errors="replace").lower()
                            if "logresp" in line:
                                verified = "verified" in line and "unverified" not in line
                                break
                        self.verified = verified
                        if not verified:
                            self._status("APRS-IS recusou a autenticação; confirme indicativo/passcode")
                            self._stop.wait(15)
                            continue
                        self._status("APRS-IS conectado e verificado · iGate RX-only (qAO)")
                        while not self._stop.is_set():
                            try:
                                line = self._queue.get(timeout=1)
                            except queue.Empty:
                                continue
                            if line is None:
                                break
                            sock.sendall((line + "\r\n").encode("latin-1"))
                            self.sent += 1
            except (OSError, ValueError) as exc:
                self._status(f"APRS-IS indisponível: {exc}")
            finally:
                self.verified = False
            if not self._stop.is_set():
                self._stop.wait(5)
