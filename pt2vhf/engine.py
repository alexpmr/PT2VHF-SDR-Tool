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

from .audio import ActivityRecorder, AudioOutput, WavRecorder
from .decoders import aprs as aprs_mod
from .decoders.afsk import AFSKDemodulator
from .decoders.tones import CTCSSDetector, DTMFDecoder
from .dsp.receiver import AUDIO_RATE, Receiver, compute_spectrum
from .sources.base import IQSource
from .timeshift import TimeShiftBuffer

log = logging.getLogger(__name__)


class ExtraReceiver:
    """Receptor adicional dentro da mesma faixa (ouvido junto com o principal)."""

    def __init__(self, sample_rate: int, freq: float, mode: str = "NFM", width: float | None = None):
        self.rx = Receiver(sample_rate)
        self.freq = float(freq)
        self.enabled = True
        self.in_span = True
        self.rx.set_mode(mode, width)
        self.rx.volume = 0.5
        self.label = ""


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
        self.hold_center = False  # True durante a varredura: o VFO não move o centro
        self.activity_rec: ActivityRecorder | None = None   # Scanner: um arquivo por transmissão
        self.vox_rec: ActivityRecorder | None = None        # botão Gravar áudio com VOX
        self.audio_listeners: list = []
        self.iq_listeners: list = []  # decoders consume original complex IQ via bounded queues
        self.iq_vox = False                                 # IQ só com transmissão
        self._iq_open_until = 0.0
        self.timeshift_seconds = 20.0
        self.timeshift: TimeShiftBuffer | None = None
        self.replay_pos: int | None = None
        self.extras: list[ExtraReceiver] = []
        self._capture: dict | None = None
        self.events: queue.Queue = queue.Queue()
        self.wf_lines: deque = deque(maxlen=200)
        self.spectrum: np.ndarray | None = None
        self.spectrum_center = 0.0
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
        self.replay_pos = None
        self.timeshift = (TimeShiftBuffer(source.sample_rate, self.timeshift_seconds)
                          if self.timeshift_seconds > 0 else None)
        for ex in self.extras:  # recria na taxa da nova fonte, preservando modo e volume
            old = ex.rx
            ex.rx = Receiver(source.sample_rate)
            ex.rx.set_mode(old.mode)
            ex.rx.set_passband(old.low, old.high)
            ex.rx.volume, ex.rx.squelch.threshold_db = old.volume, old.squelch.threshold_db
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
        for attr, kind in (("activity_rec", "activity"), ("vox_rec", "vox")):
            rec = getattr(self, attr)
            if rec is not None:
                ev = rec.close()
                setattr(self, attr, None)
                if ev:
                    self.events.put((kind, ev, ev["start"]))
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
        """Muda a frequência central (usado pelo scanner, com hold_center=True)."""
        def _do(_rx):
            if self.source:
                self.source.set_center_freq(freq)
                self._flush_source()
                self.wf_lines.clear()
                self._wf_acc = 1.0  # próxima linha sai já com o novo centro
                self._retune(self.vfo)
        self.call(_do)

    def _flush_source(self):
        q = getattr(self.source, "_q", None)
        if q is None:
            return
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break

    def _retune(self, vfo: float, force: bool = False):
        src, rx = self.source, self.rx
        if not src or not rx:
            return
        fs = src.sample_rate
        margin = fs / 2 * 0.9 - abs(rx.bandwidth) / 2
        if not src.tunable or self.hold_center:
            # gravação IQ ou scanner: centro fixo, só desloca o canal dentro da faixa
            lim = fs / 2 * 0.95
            rx.set_offset(min(max(vfo - src.center_freq, -lim), lim))
            return
        if force or abs(vfo - src.center_freq) > margin:
            # mantém o VFO afastado do pico DC do RTL-SDR
            new_c = vfo + fs / 8 if fs >= 900_000 else vfo
            if src.set_center_freq(new_c) is False:  # fora do alcance do dongle: mantém o centro
                lim = fs / 2 * 0.95
                rx.set_offset(min(max(vfo - src.center_freq, -lim), lim))
                return
            self.wf_lines.clear()
        rx.set_offset(vfo - src.center_freq)

    @property
    def center_freq(self) -> float:
        return self.source.center_freq if self.source else self.vfo

    @property
    def sample_rate(self) -> int:
        return self.source.sample_rate if self.source else 0

    # ----------------------------------------------------------- voltar no tempo
    def set_timeshift(self, seconds: float):
        """Define o tamanho do buffer (0 = desligado). Vale a partir de já."""
        self.timeshift_seconds = float(seconds)

        def _do(_rx):
            self.replay_pos = None
            src = self.source
            self.timeshift = TimeShiftBuffer(src.sample_rate, seconds) if (src and seconds > 0) else None
        if self.source is not None:
            self.call(_do)

    def start_replay(self, seconds_back: float):
        def _do(_rx):
            ts = self.timeshift
            if ts is None or ts.written == 0:
                return
            pos = ts.written - int(seconds_back * ts.sample_rate)
            self.replay_pos = max(pos, ts.oldest())
            self.events.put(("replay", self.replay_seconds_behind(), time.time()))
        self.call(_do)

    def stop_replay(self):
        def _do(rx):
            if self.replay_pos is not None:
                self.replay_pos = None
                self._retune(self.vfo)
                self.events.put(("replay_end", 0.0, time.time()))
        self.call(_do)

    def replay_seconds_behind(self) -> float:
        ts = self.timeshift
        if ts is None or self.replay_pos is None:
            return 0.0
        return (ts.written - self.replay_pos) / ts.sample_rate

    # ----------------------------------------------------------- receptores extras
    def add_extra(self, freq: float, mode: str = "NFM", width: float | None = None) -> ExtraReceiver | None:
        if self.source is None or len(self.extras) >= 4:
            return None
        ex = ExtraReceiver(self.source.sample_rate, freq, mode, width)
        self.call(lambda _rx: self.extras.append(ex))
        return ex

    def remove_extra(self, ex: ExtraReceiver):
        self.call(lambda _rx: self.extras.remove(ex) if ex in self.extras else None)

    # ----------------------------------------------------------- captura p/ assistente
    def capture_if(self, seconds: float, callback):
        """Captura `seconds` de IQ a 240 kHz centrado no VFO e chama callback(iq, fs) numa thread."""
        def _do(rx):
            rx.keep_if = True
            self._capture = {"need": int(240_000 * seconds), "chunks": [], "got": 0, "cb": callback}
        self.call(_do)

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
            if self._iq_rec and (not self.iq_vox or rx.squelch.is_open or time.monotonic() < self._iq_open_until):
                self._iq_rec.write(blk)

        fs = src.sample_rate
        for listener in tuple(self.iq_listeners):
            try:
                listener(blk, src.center_freq, fs)
            except Exception as exc:
                log.warning("IQ listener: %s", exc)
        self._wf_acc += len(blk) / fs
        if self._wf_acc >= 1.0 / self.wf_speed:
            self._wf_acc = min(self._wf_acc - 1.0 / self.wf_speed, 1.0)
            spec = compute_spectrum(blk, self.fft_size, max_frames=6)
            if spec is not None:
                self.spectrum = spec
                self.spectrum_center = src.center_freq
                self.wf_lines.append((spec, src.center_freq, fs))

        center = src.center_freq
        if self.timeshift is not None:
            self.timeshift.append(blk, center)
        rx_in = blk
        if self.replay_pos is not None and self.timeshift is not None:
            got = self.timeshift.read(self.replay_pos, len(blk))
            ts = self.timeshift
            if got is None or ts.written - self.replay_pos <= len(blk):
                self.replay_pos = None  # alcançou o ao vivo
                self.events.put(("replay_end", 0.0, time.time()))
            else:
                rx_in, rcenter = got
                self.replay_pos += len(rx_in)
                lim = fs / 2 * 0.95
                rx.set_offset(min(max(self.vfo - rcenter, -lim), lim))
        live_offset = None if rx_in is blk else self.vfo - center

        audio, raw = rx.process(rx_in)
        if live_offset is not None:
            self._retune(self.vfo)

        cap = self._capture
        if cap is not None and len(rx.last_if):
            cap["chunks"].append(rx.last_if.copy())
            cap["got"] += len(rx.last_if)
            if cap["got"] >= cap["need"]:
                self._capture = None
                rx.keep_if = False
                iq = np.concatenate(cap["chunks"])
                threading.Thread(target=cap["cb"], args=(iq, 240_000), daemon=True).start()

        if self.extras:
            mix = audio.astype(np.float32).copy()
            for ex in list(self.extras):
                off = ex.freq - center
                ex.in_span = abs(off) < fs / 2 * 0.9
                if not ex.enabled or not ex.in_span:
                    continue
                ex.rx.set_offset(off)
                a, _ = ex.rx.process(blk)
                n = min(len(a), len(mix))
                mix[:n] += a[:n]
            audio = np.tanh(mix).astype(np.float32)

        if self.decoders_enabled.get("ctcss"):
            tone = self.ctcss.process(raw) if rx.mode == "NFM" else None
            self.status["ctcss"] = tone
        tone_ok = True
        if self.tone_squelch and rx.mode == "NFM":
            tone = self.status.get("ctcss")
            if tone is None or abs(tone - self.tone_squelch) > 1.0:
                audio = np.zeros_like(audio)
                tone_ok = False
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
        for listener in self.audio_listeners:  # ex.: servidor web (áudio no navegador)
            listener(audio)
        with self._lock:
            if self._audio_rec and len(audio):
                self._audio_rec.write(audio)
        sq_active = rx.squelch.threshold_db > -149 or self.tone_squelch is not None
        opened = sq_active and rx.squelch.is_open and tone_ok
        if opened:
            self._iq_open_until = time.monotonic() + 1.5
        for rec, kind in ((self.activity_rec, "activity"), (self.vox_rec, "vox")):
            if rec is not None:
                ev = rec.process(rx.rec_audio_raw, opened, self.vfo, rx.mode, rx.signal_db)
                if ev:
                    self.events.put((kind, ev, ev["start"]))
        if self.audio_tap:
            self.audio_tap(audio, raw)

    def _loop(self):
        while self._running:
            pop = getattr(self.source, "pop_messages", None)
            if pop is not None:
                for msg in pop():
                    self.events.put(("source_msg", msg, time.time()))
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
