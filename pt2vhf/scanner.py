"""Scanner por espectro: detecta sinais direto no FFT, salta entre segmentos de uma faixa,
registra frequências ativas (descoberta) e pode parar para escutar (com canal prioritário).

O scanner não depende do squelch de áudio: decide pela relação sinal/ruído no espectro,
o que permite varrer milhares de canais por segundo com um RTL-SDR (2,4 MHz por segmento).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ScanRange:
    name: str
    start: float
    end: float
    resolution: int     # arredondamento das frequências encontradas (Hz)
    mode: str
    bandwidth: float
    snr_db: float = 10.0
    notes: str = ""


SCAN_PRESETS = [
    ScanRange("Aviação VHF (118–137 MHz)", 118.0e6, 137.0e6, 5000, "AM", 8000, 10),
    ScanRange("Marítimo VHF (156–162 MHz)", 156.0e6, 162.05e6, 5000, "NFM", 12000),
    ScanRange("Radioamador 2 m (144–148 MHz)", 144.0e6, 148.0e6, 5000, "NFM", 12000),
    ScanRange("Radioamador 70 cm (430–440 MHz)", 430.0e6, 440.0e6, 5000, "NFM", 12000),
    ScanRange("VHF serviços (148–174 MHz)", 148.0e6, 174.0e6, 5000, "NFM", 12000),
    ScanRange("UHF serviços (450–470 MHz)", 450.0e6, 470.0e6, 5000, "NFM", 12000),
    ScanRange("Rádio comunicador FRS (462–468 MHz)", 462.5e6, 467.75e6, 2500, "NFM", 12000),
    ScanRange("PMR446 (446,0–446,2 MHz)", 446.0e6, 446.2e6, 2500, "NFM", 8000),
    ScanRange("PX 11 m (26,96–27,41 MHz)", 26.96e6, 27.41e6, 5000, "AM", 8000, notes="Requer HF"),
    ScanRange("Radiossondas (400–406 MHz)", 400.0e6, 406.0e6, 5000, "NFM", 12000),
    ScanRange("FM broadcast (76–108 MHz)", 76.0e6, 108.0e6, 100000, "WFM", 180000, 15),
    ScanRange("Ondas curtas 49 m (5,9–6,2 MHz)", 5.9e6, 6.2e6, 5000, "AM", 8000, notes="Requer HF"),
    ScanRange("Ondas curtas 31 m (9,4–9,9 MHz)", 9.4e6, 9.9e6, 5000, "AM", 8000, notes="Requer HF"),
    ScanRange("Ondas curtas 25 m (11,6–12,1 MHz)", 11.6e6, 12.1e6, 5000, "AM", 8000, notes="Requer HF"),
    ScanRange("Ondas curtas 19 m (15,1–15,8 MHz)", 15.1e6, 15.8e6, 5000, "AM", 8000, notes="Requer HF"),
]


@dataclass
class Hit:
    freq: float
    first_seen: float
    last_seen: float
    hits: int = 1
    max_snr: float = 0.0
    max_db: float = -200.0
    seconds_active: float = 0.0
    listened: bool = False


@dataclass
class Detection:
    freq: float
    level_db: float
    snr_db: float


def detect_signals(spec_db: np.ndarray, center: float, fs: float, f0: float, f1: float,
                   resolution: float, snr_db: float, usable: float = 0.85,
                   dc_guard_hz: float = 3000.0, gap_bins: int = 2) -> tuple[list[Detection], float]:
    """Encontra sinais num espectro (dBFS). Retorna (detecções, piso de ruído)."""
    n = len(spec_db)
    bin_hz = fs / n
    freqs = center + (np.arange(n) - n / 2) * bin_hz
    valid = (np.abs(freqs - center) <= fs / 2 * usable) & (freqs >= f0) & (freqs <= f1)
    valid &= np.abs(freqs - center) > dc_guard_hz
    if valid.sum() < 8:
        return [], -200.0
    floor = float(np.median(spec_db[valid]))
    above = valid & (spec_db > floor + snr_db)
    idx = np.flatnonzero(above)
    out: list[Detection] = []
    if len(idx) == 0:
        return out, floor
    # agrupa bins próximos (um sinal FM ocupa vários bins)
    groups, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > gap_bins + 1:
            groups.append((start, prev))
            start = i
        prev = i
    groups.append((start, prev))
    for a, b in groups:
        seg = spec_db[a:b + 1]
        p = 10 ** (seg / 10)
        fc = float(np.sum(freqs[a:b + 1] * p) / np.sum(p))  # centróide de potência
        if resolution > 0:
            fc = round(fc / resolution) * resolution
        if not (f0 <= fc <= f1):
            continue
        peak = float(seg.max())
        out.append(Detection(fc, peak, peak - floor))
    out.sort(key=lambda d: -d.snr_db)
    return out, floor


def level_at(spec_db: np.ndarray, center: float, fs: float, freq: float, half_bw: float) -> float | None:
    n = len(spec_db)
    bin_hz = fs / n
    k = (freq - center) / bin_hz + n / 2
    w = max(1, int(half_bw / bin_hz))
    a, b = int(k) - w, int(k) + w + 1
    if a < 0 or b > n:
        return None
    return float(spec_db[a:b].max())


@dataclass
class ScannerConfig:
    start: float
    end: float
    resolution: int = 5000
    snr_db: float = 10.0
    mode: str = "NFM"
    bandwidth: float = 12000
    listen: bool = False           # False = só descobrir; True = parar no sinal
    dwell_lines: int = 4           # linhas de espectro por segmento
    settle_lines: int = 2          # linhas descartadas após mudar o centro
    resume_s: float = 2.0          # retomar após o sinal cair
    max_listen_s: float = 0.0      # 0 = sem limite
    cooldown_s: float = 8.0        # ignora a frequência por este tempo após escutá-la
    priority_freq: float | None = None
    priority_interval_s: float = 3.0
    lockouts: set = field(default_factory=set)


class SpectrumScanner:
    """Máquina de estados do scanner. Alimentada pelas linhas de espectro do motor.

    `engine` precisa expor: hold_center (bool), set_center(hz), tune(hz),
    center_freq e sample_rate.
    """

    def __init__(self, engine, cfg: ScannerConfig):
        self.engine = engine
        self.cfg = cfg
        self.hits: dict[float, Hit] = {}
        self.running = False
        self.state = "idle"
        self.listen_freq: float | None = None
        self.sweeps = 0
        self.floor_db = -200.0
        self._seg = 0
        self._segments: list[float] = []
        self._lines = 0
        self._maxhold = None
        self._target_center = None
        self._last_active = 0.0
        self._listen_start = 0.0
        self._cooldown: dict[float, float] = {}
        self._last_priority = 0.0
        self._resume_center = None
        self._now = 0.0

    # ------------------------------------------------------------- controle
    def start(self, now: float = 0.0):
        fs = self.engine.sample_rate
        usable = fs * 0.8
        f0, f1 = sorted((self.cfg.start, self.cfg.end))
        self.cfg.start, self.cfg.end = f0, f1
        span = f1 - f0
        if span <= usable:
            # um só segmento; se couber, deixa o pico DC (centro) fora da faixa
            c = f1 + 10_000 if span + 10_000 <= usable / 2 else (f0 + f1) / 2
            self._segments = [c]
        else:
            n = int(np.ceil(span / usable))
            self._segments = [f0 + usable / 2 + k * usable for k in range(n)]
        self.running = True
        self.engine.hold_center = True
        self._seg = -1
        self._last_priority = now
        self._next_segment()

    def stop(self):
        self.running = False
        self.state = "idle"
        self.listen_freq = None
        self.engine.hold_center = False

    def lockout(self, freq: float):
        self.cfg.lockouts.add(round(freq))
        self.hits.pop(self._match(freq) or -1, None)

    def _locked(self, f: float) -> bool:
        tol = max(self.cfg.resolution, self.cfg.bandwidth / 2)
        return any(abs(f - x) < tol for x in self.cfg.lockouts)

    def _match(self, f: float) -> float | None:
        tol = max(self.cfg.resolution * 1.5, self.cfg.bandwidth / 3)
        best = None
        for k in self.hits:
            if abs(k - f) <= tol and (best is None or abs(k - f) < abs(best - f)):
                best = k
        return best

    def _goto_center(self, c: float, after: str = "dwell"):
        self._target_center = c
        self._lines = 0
        self._maxhold = None
        self._after_settle = after
        self.engine.set_center(c)
        self.state = "settle"

    def _next_segment(self):
        self._seg += 1
        if self._seg >= len(self._segments):
            self._seg = 0
            self.sweeps += 1
        c = self._segments[self._seg]
        if len(self._segments) == 1 and self._target_center == c and self.state != "idle":
            self._lines = 0
            self._maxhold = None
            self.state = "dwell"
            return
        self._goto_center(c)

    # ------------------------------------------------------------- alimentação
    def feed(self, spec: np.ndarray, center: float, fs: float, now: float) -> list[tuple]:
        """Processa uma linha de espectro. Retorna eventos para a interface."""
        if not self.running:
            return []
        self._now = now
        if self._target_center is not None and abs(center - self._target_center) > 1:
            return []  # linha antiga (antes da mudança de centro)
        ev: list[tuple] = []
        if self.state == "settle":
            self._lines += 1
            if self._lines >= self.cfg.settle_lines:
                self.state = getattr(self, "_after_settle", "dwell")
                self._lines = 0
                self._maxhold = None
            return ev
        if self.state in ("dwell", "priority"):
            self._maxhold = spec.copy() if self._maxhold is None else np.maximum(self._maxhold, spec)
            self._lines += 1
            if self._lines < self.cfg.dwell_lines:
                return ev
            if self.state == "priority":
                return self._finish_priority(center, fs, now)
            return self._finish_dwell(center, fs, now)
        if self.state == "listen":
            lvl = level_at(spec, center, fs, self.listen_freq, max(self.cfg.bandwidth / 2, 2000))
            active = lvl is not None and lvl > self.floor_db + self.cfg.snr_db * 0.7
            h = self.hits.get(self._match(self.listen_freq) or -1)
            if active:
                self._last_active = now
                if h:
                    h.last_seen = now
                    h.seconds_active += 1.0 / max(self.engine_lines_per_s(), 1)
            too_long = self.cfg.max_listen_s > 0 and now - self._listen_start > self.cfg.max_listen_s
            if now - self._last_active > self.cfg.resume_s or too_long:
                self._cooldown[self.listen_freq] = now
                ev.append(("resume", self.listen_freq))
                self.listen_freq = None
                self._resume_after_listen()
            return ev
        return ev

    def engine_lines_per_s(self) -> float:
        return float(getattr(self.engine, "wf_speed", 20))

    def _finish_dwell(self, center, fs, now) -> list[tuple]:
        ev = []
        dets, floor = detect_signals(self._maxhold, center, fs, self.cfg.start, self.cfg.end,
                                     self.cfg.resolution, self.cfg.snr_db)
        self.floor_db = floor
        for d in dets:
            if self._locked(d.freq):
                continue
            k = self._match(d.freq)
            if k is None:
                h = Hit(d.freq, now, now, 1, d.snr_db, d.level_db)
                self.hits[d.freq] = h
                ev.append(("hit", h, True))
            else:
                h = self.hits[k]
                h.hits += 1
                h.last_seen = now
                h.max_snr = max(h.max_snr, d.snr_db)
                h.max_db = max(h.max_db, d.level_db)
                h.seconds_active += self.cfg.dwell_lines / max(self.engine_lines_per_s(), 1)
                ev.append(("hit", h, False))
        # prioridade
        p = self.cfg.priority_freq
        if p and now - self._last_priority >= self.cfg.priority_interval_s:
            self._last_priority = now
            self._resume_center = center
            if abs(p - center) <= fs / 2 * 0.85:
                self.state, self._lines, self._maxhold = "priority", 0, None
            else:
                self._goto_center(p + fs / 8, after="priority")
            return ev
        if self.cfg.listen:
            for d in dets:
                if self._locked(d.freq):
                    continue
                cd = [f for f, t in self._cooldown.items() if abs(f - d.freq) < self.cfg.bandwidth and now - t < self.cfg.cooldown_s]
                if cd:
                    continue
                self._start_listen(d.freq, now)
                ev.append(("listen", d.freq))
                return ev
        self._next_segment()
        ev.append(("segment", self._segments[self._seg], self._seg, len(self._segments)))
        return ev

    def _finish_priority(self, center, fs, now):
        p = self.cfg.priority_freq
        lvl = level_at(self._maxhold, center, fs, p, max(self.cfg.bandwidth / 2, 2000))
        _dets, floor = detect_signals(self._maxhold, center, fs, center - fs / 2, center + fs / 2,
                                      self.cfg.resolution, self.cfg.snr_db)
        if lvl is not None and lvl > floor + self.cfg.snr_db:
            self.floor_db = floor
            self._start_listen(p, now)
            return [("listen", p), ("priority", p)]
        self._resume_after_listen()
        return []

    def _start_listen(self, f, now):
        self.state = "listen"
        self.listen_freq = f
        self._last_active = now
        self._listen_start = now
        h = self.hits.get(self._match(f) or -1)
        if h:
            h.listened = True
        self.engine.tune(f)

    def _resume_after_listen(self):
        rc = self._resume_center
        self._resume_center = None
        if rc is not None and abs(rc - (self._target_center or rc)) > 1:
            self._goto_center(rc)
            return
        self._next_segment()

    # ------------------------------------------------------------- utilidades
    def sorted_hits(self) -> list[Hit]:
        return sorted(self.hits.values(), key=lambda h: h.freq)

    def channels_per_second(self) -> float:
        lps = self.engine_lines_per_s()
        per_seg = (self.cfg.dwell_lines + self.cfg.settle_lines) / lps
        chans = self.engine.sample_rate * 0.8 / max(self.cfg.resolution, 1)
        return chans / per_seg
