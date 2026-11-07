"""Motor do receptor: thread de processamento que liga fonte -> DSP -> áudio/decodificadores.

A interface conversa com o motor apenas por métodos thread-safe:
  - comandos são enfileirados e executados entre blocos (sem condições de corrida)
  - resultados (espectro, nível, eventos de decodificação) são lidos por polling
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

from .audio import AudioOutput, WavRecorder
from .decoders import aprs as aprs_mod
from .decoders.afsk import AFSKDemodulator
from .decoders.tones import CTCSSDetector, DTMFDecoder
from .dsp.receiver import AUDIO_RATE, Receiver, compute_spectrum
from .sources.base import IQSource

log = logging.getLogger(__name__)


class Engine:
    def __init__(self, audio: AudioOutput | None = None):
        self.source: IQSource | None = None
        self.rx: Receiver | None = None
        self.audio = audio
        self.vfo = 145.570e6
        self.fft_size = 4096
        self.wf_speed = 20.0
        self.decoders_enabled = {"aprs": True, "dtmf": True, "ctcss": True}
        self.tone_squelch: float | None = None  # CTCSS exigido para abrir o áudio
        self.events: queue.Queue = queue.Queue()
        self.wf_lines: deque = deque(maxlen=200)
        self.spectrum: np.ndarray | None = None
        self.status = {"signal_db": -150.0, "sq_open": False, "ctcss": None, "dropped": 0,
                       "cpu": 0.0, "running": False, "audio_level": 0.0}
        self._cmds: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._wf_acc = 0.0
        self._audio_rec: WavRecorder | None = None
        self._iq_rec: WavRecorder | None = None
        self._lock = threading.Lock()
        self.audio_tap = None  # callback opcional (testes)
        self._make_decoders()

    def _make_decoders(self):
        self.afsk = AFSKDemodulator(self._on_ax25, AUDIO_RATE)
        self.dtmf = DTMFDecoder(lambda d: self.events.put(("dtmf", d, time.time())), AUDIO_RATE)
        self.ctcss = CTCSSDetector(AUDIO_RATE)

    def _on_ax25(self, frame):
        try:
            pkt = aprs_mod.parse(frame)
        except Exception as e:  # noqa: BLE001
            log.warning("Falha no parse APRS: %s", e)
            return
        self.events.put(("aprs", pkt, time.time()))

    # ----------------------------------------------------------- ciclo de vida
    def start(self, source: IQSource):
        self.stop()
        self.source = source
        self.rx = Receiver(source.sample_rate)
        self._make_decoders()
        self._retune(self.vfo, force=True)
        source.start()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="dsp")
        self._thread.start()
        self.status["running"] = True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self.source:
            try:
                self.source.close()
            except Exception as e:  # noqa: BLE001
                log.warning("Erro ao fechar fonte: %s", e)
            self.source = None
        self.stop_audio_recording()
        self.stop_iq_recording()
        self.status["running"] = False

    @property
    def running(self) -> bool:
        return self._running

    # ----------------------------------------------------------- comandos
    def call(self, fn):
        """Executa `fn(rx)` na thread DSP entre blocos (ou já, se parado)."""
        if self._running:
            self._cmds.put(fn)
        elif self.rx is not None:
            fn(self.rx)

    def tune(self, freq: float):
        self.vfo = float(freq)
        if self._running:
            self._cmds.put(lambda _rx: self._retune(self.vfo))
        elif self.rx:
            self._retune(self.vfo)

    def set_center(self, freq: float):
        def _do(_rx):
            if self.source:
                self.source.set_center_freq(freq)
                self._retune(self.vfo)
        self.call(_do)

    def _retune(self, vfo: float, force: bool = False):
        src, rx = self.source, self.rx
        if not src or not rx:
            return
        fs = src.sample_rate
        margin = fs / 2 * 0.9 - abs(rx.bandwidth) / 2
        if not src.tunable:
            # gravação: só é possível sintonizar dentro da faixa gravada
            lim = fs / 2 * 0.95
            rx.set_offset(min(max(vfo - src.center_freq, -lim), lim))
            return
        if force or abs(vfo - src.center_freq) > margin:
            # mantém o VFO afastado do pico DC do RTL-SDR
            new_c = vfo + fs / 8 if fs >= 900_000 else vfo
            src.set_center_freq(new_c)
            self.wf_lines.clear()
        rx.set_offset(vfo - src.center_freq)

    @property
    def center_freq(self) -> float:
        return self.source.center_freq if self.source else self.vfo

    @property
    def sample_rate(self) -> int:
        return self.source.sample_rate if self.source else 0

    # ----------------------------------------------------------- gravação
    def start_audio_recording(self, folder: str) -> Path:
        name = datetime.now().strftime(f"PT2VHF_%Y%m%d_%H%M%S_{int(self.vfo)}Hz_AF.wav")
        p = Path(folder) / name
        with self._lock:
            self._audio_rec = WavRecorder(p, AUDIO_RATE, 1)
        return p

    def stop_audio_recording(self):
        with self._lock:
            if self._audio_rec:
                self._audio_rec.close()
                self._audio_rec = None

    def start_iq_recording(self, folder: str) -> Path:
        name = datetime.now().strftime(f"PT2VHF_%Y%m%d_%H%M%S_{int(self.center_freq)}Hz_IQ.wav")
        p = Path(folder) / name
        with self._lock:
            self._iq_rec = WavRecorder(p, self.sample_rate, 2)
        return p

    def stop_iq_recording(self):
        with self._lock:
            if self._iq_rec:
                self._iq_rec.close()
                self._iq_rec = None

    @property
    def recording_audio(self):
        return self._audio_rec is not None

    @property
    def recording_iq(self):
        return self._iq_rec is not None

    # ----------------------------------------------------------- processamento
    def process_block(self, blk: np.ndarray):
        """Processa um bloco (também usado diretamente pelos testes)."""
        rx, src = self.rx, self.source
        while True:
            try:
                fn = self._cmds.get_nowait()
            except queue.Empty:
                break
            try:
                fn(rx)
            except Exception as e:  # noqa: BLE001
                log.exception("Comando falhou: %s", e)

        blk = blk - np.mean(blk)  # remove DC (pico central do RTL-SDR)
        with self._lock:
            if self._iq_rec:
                self._iq_rec.write(blk)

        fs = src.sample_rate
        self._wf_acc += len(blk) / fs
        if self._wf_acc >= 1.0 / self.wf_speed:
            self._wf_acc = min(self._wf_acc - 1.0 / self.wf_speed, 1.0)
            spec = compute_spectrum(blk, self.fft_size, max_frames=6)
            if spec is not None:
                self.spectrum = spec
                self.wf_lines.append((spec, src.center_freq, fs))

        audio, raw = rx.process(blk)

        if self.decoders_enabled.get("ctcss"):
            tone = self.ctcss.process(raw) if rx.mode == "NFM" else None
            self.status["ctcss"] = tone
        if self.tone_squelch and rx.mode == "NFM":
            tone = self.status.get("ctcss")
            if tone is None or abs(tone - self.tone_squelch) > 1.0:
                audio = np.zeros_like(audio)
        if rx.mode == "NFM":
            if self.decoders_enabled.get("aprs"):
                self.afsk.process(raw)
            if self.decoders_enabled.get("dtmf"):
                self.dtmf.process(raw)

        self.status["signal_db"] = rx.signal_db
        self.status["sq_open"] = rx.squelch.is_open
        self.status["audio_level"] = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if self.audio is not None:
            self.audio.write(audio)
        with self._lock:
            if self._audio_rec and len(audio):
                self._audio_rec.write(audio)
        if self.audio_tap:
            self.audio_tap(audio, raw)

    def _loop(self):
        while self._running:
            blk = self.source.read(timeout=0.5) if self.source else None
            if blk is None:
                if self.source and not self.source._running:
                    self.events.put(("error", "A fonte de sinal parou.", time.time()))
                    break
                continue
            t0 = time.perf_counter()
            try:
                self.process_block(blk)
            except Exception as e:  # noqa: BLE001
                log.exception("Erro DSP: %s", e)
            dt = time.perf_counter() - t0
            self.status["cpu"] = 0.9 * self.status["cpu"] + 0.1 * (dt / (len(blk) / self.source.sample_rate))
            self.status["dropped"] = self.source.dropped
        self._running = False
        self.status["running"] = False
