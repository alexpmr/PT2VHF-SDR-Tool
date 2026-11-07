"""Assistente de sintonia: análise automática do sinal sem processar o áudio.

- estimate_ssb_offset: estima o erro de sintonia de uma fonia SSB pela estrutura harmônica
  da voz. A voz sonora é um "pente" de harmônicos em k·f0; com erro de sintonia Δ eles aparecem
  em Δ + k·f0. Num único quadro Δ só é determinado módulo f0, mas a entonação faz f0 variar ao
  longo do tempo enquanto Δ é constante: acumulando a evidência de vários quadros, só o Δ
  verdadeiro se mantém. Atua no VFO, não no áudio.
- detect_mode: classifica o sinal (WFM, NFM, AM, USB/LSB, CW) por largura ocupada,
  presença de portadora, envoltória constante e simetria espectral.
- occupied_band: bordas do sinal, para o filtro adaptativo.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal

SSB_RATE = 8000


def _to_rate(iq: np.ndarray, fs: int, target: int) -> np.ndarray:
    if fs == target:
        return iq
    g = np.gcd(int(fs), int(target))
    return signal.resample_poly(iq, target // g, fs // g)


def estimate_ssb_offset(iq: np.ndarray, fs: int, sideband: str = "USB",
                        max_offset: float = 600.0) -> tuple[float, float] | None:
    """Retorna (Δ em Hz, confiança 0..1) ou None se não houver voz suficiente.

    `iq` é a banda base complexa centrada no VFO atual. Para corrigir, some Δ ao VFO.
    """
    x = _to_rate(np.asarray(iq, np.complex64), fs, SSB_RATE)
    if sideband == "LSB":
        x = np.conj(x)  # espelha: LSB vira USB
    n, hop, nfft = 512, 256, 4096
    if len(x) < n * 4:
        return None
    win = signal.windows.hann(n, sym=False).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::hop] * win
    spec = np.abs(np.fft.fft(frames, nfft, axis=1)) ** 2
    freqs = np.fft.fftfreq(nfft, 1 / SSB_RATE)
    order = np.argsort(freqs)
    freqs, spec = freqs[order], spec[:, order]
    band = (freqs > -max_offset - 400) & (freqs < 3400 + max_offset)
    freqs, spec = freqs[band], spec[:, band]
    logs = 10 * np.log10(spec + 1e-12)
    # branqueamento: destaca picos em relação ao envelope local (~150 Hz)
    k = max(3, int(150 / (SSB_RATE / nfft)) | 1)
    smooth = signal.medfilt(logs, (1, k))
    peaks = np.clip(logs - smooth, 0, 20)
    # quadros sonoros: energia alta e espectro "picudo"
    energy = logs.max(axis=1)
    peaky = peaks.mean(axis=1)
    voiced = (energy > np.percentile(energy, 40)) & (peaky > np.percentile(peaky, 30))
    if voiced.sum() < 8:
        return None
    peaks = peaks[voiced]
    # borda inferior da voz no espectro médio: o filtro SSB do transmissor corta em ~300 Hz,
    # o que desempata os "aliases" Δ ± f0 deixados pela análise harmônica
    mean_spec = 10 * np.log10(np.mean(spec[voiced], axis=0) + 1e-12)
    ms = np.convolve(mean_spec, np.ones(9) / 9, "same")
    fl = float(np.percentile(ms, 20))
    hot = np.flatnonzero(ms > fl + 0.5 * (ms.max() - fl))
    edge = float(freqs[hot[0]]) - 300.0 if len(hot) else 0.0
    if len(peaks) > 150:  # limita o custo: quadros espalhados no tempo
        peaks = peaks[np.linspace(0, len(peaks) - 1, 150).astype(int)]
    peaks = peaks.astype(np.float32)

    df = freqs[1] - freqs[0]
    deltas = np.arange(-max_offset, max_offset + 0.1, 5.0)
    f0s = np.arange(75.0, 330.0, 2.0)
    kmax = int(2800 / f0s.min()) + 1
    ks = np.arange(1, kmax + 1)
    harm = f0s[:, None] * ks[None, :]                        # (nf0, K)
    valid = (harm >= 300) & (harm <= 2800)
    inter = harm + 0.5 * f0s[:, None]
    nvalid = valid.sum(axis=1).astype(np.float32)

    def sample(p, pos):
        idx = (pos - freqs[0]) / df
        i0 = np.clip(idx.astype(int), 0, len(freqs) - 2)
        w = np.clip(idx - i0, 0, 1)
        return p[..., i0] * (1 - w) + p[..., i0 + 1] * w

    total = np.zeros(len(deltas), np.float64)
    for p in peaks:
        on = sample(p, deltas[:, None, None] + harm[None])        # (nΔ, nf0, K)
        off = sample(p, deltas[:, None, None] + inter[None])
        score = ((on - off) * valid[None]).sum(axis=2) / nvalid[None]
        total += score.max(axis=1)
    total /= len(peaks)
    harmonicity = float(total.max())
    estimate_ssb_offset.last_harmonicity = harmonicity  # usado por _ssb_side
    if harmonicity < 6.0:  # sem estrutura harmônica (ruído, portadora, dados)
        return None
    # escolhe entre os máximos locais combinando harmônicos e a borda da voz (σ ≈ 90 Hz)
    prior = np.exp(-0.5 * ((deltas - edge) / 90.0) ** 2)
    rel = (total - np.median(total)) / (harmonicity - np.median(total) + 1e-9)
    best = int(np.argmax(np.clip(rel, 0, None) * (0.35 + 0.65 * prior)))
    d0 = deltas[best]
    fine = np.arange(d0 - 6, d0 + 6.1, 1.0)
    ftot = np.zeros(len(fine))
    for p in peaks:
        on = sample(p, fine[:, None, None] + harm[None])
        off = sample(p, fine[:, None, None] + inter[None])
        ftot += (((on - off) * valid[None]).sum(axis=2) / nvalid[None]).max(axis=1)
    delta = float(fine[int(np.argmax(ftot))])
    # confiança: destaque do pico sobre o segundo melhor (fora de ±40 Hz), relativo à mediana
    far = np.abs(deltas - d0) > 40
    second = total[far].max() if far.any() else 0.0
    peak, med = total[best], float(np.median(total))
    conf = float(np.clip((peak - second) / (peak - med + 1e-9) * 2.5, 0, 1))
    if sideband == "LSB":
        delta = -delta
    return delta, conf


@dataclass
class ModeGuess:
    mode: str
    bandwidth: float
    center_offset: float    # deslocamento sugerido do VFO (Hz)
    confidence: float
    reason: str


def _psd(iq: np.ndarray, fs: int, nfft: int):
    f, p = signal.welch(iq, fs=fs, nperseg=nfft, return_onesided=False, detrend=False)
    o = np.argsort(f)
    return f[o], 10 * np.log10(p[o] + 1e-20)


def occupied_band(iq: np.ndarray, fs: int, search_hz: float = 120_000, thresh_db: float = 12.0,
                  nfft: int = 4096, gap_hz: float = 1200.0) -> tuple[float, float, float] | None:
    """Bordas (low, high) do sinal mais próximo de 0 Hz e o piso de ruído (dB)."""
    f, p = _psd(iq, fs, nfft)
    m = np.abs(f) <= min(search_hz, fs / 2 * 0.85)
    f, p = f[m], p[m]
    k = max(1, int(round(150 / (fs / nfft))))
    ps = np.convolve(p, np.ones(k) / k, "same")
    floor = float(np.percentile(ps, 5))
    thr = max(floor + thresh_db, float(ps.max()) - 35.0)
    above = ps > thr
    if not above.any():
        return None
    idx = np.flatnonzero(above)
    near = idx[np.argmin(np.abs(f[idx]))]
    if abs(f[near]) > 15_000:
        return None
    gap = max(2, int(gap_hz / (fs / nfft)))
    lo = hi = near
    while True:
        nxt = idx[(idx < lo) & (idx >= lo - gap)]
        if not len(nxt):
            break
        lo = int(nxt.min())
    while True:
        nxt = idx[(idx > hi) & (idx <= hi + gap)]
        if not len(nxt):
            break
        hi = int(nxt.max())
    return float(f[lo]), float(f[hi]), floor


def _ssb_side(iq: np.ndarray, fs: int, lo: float, hi: float):
    """Decide USB/LSB pela voz: o pente de harmônicos só fica ancorado a uma portadora fixa
    no lado certo. Retorna (modo, deslocamento da portadora) ou None."""
    n = min(len(iq), int(fs * 3))
    seg = iq[:n]
    t = np.arange(n) / fs
    best = None
    for mode, carrier in (("USB", lo - 300.0), ("LSB", hi + 300.0)):
        x = seg * np.exp(-2j * np.pi * carrier * t).astype(np.complex64)
        r = estimate_ssb_offset(x, fs, mode)
        h = getattr(estimate_ssb_offset, "last_harmonicity", 0.0) if r else 0.0
        if r and (best is None or h > best[2]):
            best = (mode, carrier + r[0], h)
    return None if best is None else best[:2]


def detect_mode(iq: np.ndarray, fs: int, freq_hz: float | None = None) -> ModeGuess | None:
    """Classifica o sinal centrado (aprox.) em 0 Hz numa banda base de `fs` (ex.: 240 kHz)."""
    iq = np.asarray(iq, np.complex64)
    wide = occupied_band(iq, fs, thresh_db=10)
    if wide is not None and wide[1] - wide[0] > 60_000:
        w = wide[1] - wide[0]
        return ModeGuess("WFM", min(max(w * 1.1, 150_000), 200_000), (wide[0] + wide[1]) / 2, 0.9,
                         f"largura ocupada {w / 1e3:.0f} kHz")
    band = occupied_band(iq, fs, search_hz=40_000)
    if band is None:
        return None
    lo, hi, floor = band
    width = hi - lo
    center = (lo + hi) / 2
    # isola o sinal e analisa envoltória e portadora
    nyq = fs / 2
    bw = max(width, 300) / 2 * 1.15
    taps = signal.firwin(255, min(bw / nyq, 0.99))
    sh = np.exp(-2j * np.pi * center * np.arange(len(iq)) / fs).astype(np.complex64)
    y = signal.lfilter(taps, 1, iq * sh)[300:]
    env = np.abs(y)
    cv = float(np.std(env) / (np.mean(env) + 1e-12))
    f, p = _psd(iq, fs, 16384 if fs > 48_000 else 4096)
    inb = (f >= lo) & (f <= hi)
    lin = 10 ** (p[inb] / 10)
    pk = int(np.argmax(lin))
    carrier_ratio = float(lin[pk] / (lin.sum() + 1e-20))
    carrier_f = float(f[inb][pk])
    keyed = float(np.mean(env < 0.25 * np.percentile(env, 95)))

    if width < 3_000 and keyed > 0.15 and (carrier_ratio > 0.2 or width < 700):
        return ModeGuess("CW", 500, carrier_f, 0.85, f"portadora manipulada ({keyed * 100:.0f}% do tempo sem sinal)")
    if width < 700:
        return ModeGuess("CW", 500, carrier_f, 0.6, f"sinal estreito ({width:.0f} Hz)")
    if cv < 0.35 and 3_000 <= width <= 30_000:
        return ModeGuess("NFM", 12_000 if width > 7_000 else 8_000, center, 0.85,
                         f"envoltória constante, {width / 1e3:.1f} kHz")
    if carrier_ratio > 0.25 and width > 1_000 and abs((carrier_f - lo) - (hi - carrier_f)) < 0.35 * width:
        return ModeGuess("AM", min(max(width * 1.2, 5_000), 12_000), carrier_f, 0.8,
                         f"portadora com bandas laterais simétricas, {width / 1e3:.1f} kHz")
    if 1_200 <= width <= 4_500 and carrier_ratio < 0.25:
        side = _ssb_side(iq, fs, lo, hi)
        if side is not None:
            mode, carrier = side
            return ModeGuess(mode, 2700, carrier, 0.8,
                             f"voz sem portadora, {width / 1e3:.1f} kHz; banda lateral pelos harmônicos")
        usb = freq_hz is None or freq_hz >= 10e6
        mode = "USB" if usb else "LSB"
        return ModeGuess(mode, 2700, lo - 300 if usb else hi + 300, 0.5,
                         f"sem portadora, {width / 1e3:.1f} kHz; {mode} pela convenção da faixa")
    if width <= 30_000 and cv < 0.5:
        return ModeGuess("NFM", 12_000, center, 0.5, f"provável FM, {width / 1e3:.1f} kHz")
    return ModeGuess("AM", min(max(width, 5_000), 12_000), center, 0.4, f"sinal de {width / 1e3:.1f} kHz")


def adaptive_passband(iq: np.ndarray, fs: int, mode: str, low: float, high: float) -> tuple[float, float] | None:
    """Sugere bordas do filtro ajustadas ao sinal (mantendo o lado correto em SSB/CW)."""
    band = occupied_band(iq, fs, search_hz=max(abs(low), abs(high)) * 3 + 5_000, thresh_db=10)
    if band is None:
        return None
    lo, hi, _ = band
    margin = 150 if mode in ("USB", "LSB", "CW") else 600
    if mode == "USB":
        return max(100.0, lo - margin), min(4_000.0, hi + margin)
    if mode == "LSB":
        return max(-4_000.0, lo - margin), min(-100.0, hi + margin)
    if mode == "CW":
        w = max(100.0, min(1_000.0, (hi - lo) + 2 * margin))
        return -w / 2, w / 2
    half = max(abs(lo), abs(hi)) + margin
    lim = 100_000 if mode == "WFM" else 15_000
    minimum = {"AM": 2_500, "NFM": 4_000, "WFM": 50_000}.get(mode, 1_500)
    half = min(max(half, minimum), lim)
    return -half, half


def _peak_offset(iq: np.ndarray, fs: int, lo: float, hi: float) -> float | None:
    """Frequência do pico mais forte em [lo, hi] com interpolação parabólica (sub-bin)."""
    nfft = 65536 if fs > 48_000 else 16384
    nfft = min(nfft, 1 << int(np.floor(np.log2(max(len(iq), 1024)))))
    f, p = _psd(iq, fs, nfft)
    m = (f >= lo) & (f <= hi)
    if m.sum() < 3:
        return None
    idx = np.flatnonzero(m)
    k = idx[int(np.argmax(p[m]))]
    if 0 < k < len(p) - 1:
        a, b, c = p[k - 1], p[k], p[k + 1]
        den = a - 2 * b + c
        d = 0.5 * (a - c) / den if den != 0 else 0.0
        return float(f[k] + d * (f[1] - f[0]))
    return float(f[k])


def fine_tune(iq: np.ndarray, fs: int, mode: str, vfo: float, step: float = 0.0,
              search_hz: float | None = None) -> tuple[float, str] | None:
    """Correção (Hz, explicação) para ficar exatamente na transmissão perto do VFO; None se não houver sinal.

    AM/CW: portadora. NFM/WFM/DSB: centro do sinal (encaixado no canal do passo quando coerente).
    USB/LSB: portadora suprimida pelos harmônicos da voz.
    """
    iq = np.asarray(iq, np.complex64)
    if mode in ("USB", "LSB"):
        r = estimate_ssb_offset(iq, fs, mode)
        return None if r is None else (r[0], f"voz SSB (confiança {r[1] * 100:.0f}%)")
    search = search_hz or {"CW": 1_500, "AM": 6_000, "WFM": 120_000}.get(mode, 15_000)
    band = occupied_band(iq, fs, search_hz=search + 5_000)
    if band is None:
        return None
    lo, hi, _ = band
    if mode in ("AM", "CW"):
        pk = _peak_offset(iq, fs, max(lo, -search), min(hi, search))
        if pk is None:
            return None
        delta, why = pk, "portadora"
    else:
        delta, why = (lo + hi) / 2, "centro do sinal"
    if abs(delta) > search:
        return None
    target = vfo + delta
    if step and mode in ("NFM", "WFM", "AM") and step >= 2_500:
        snapped = round(target / step) * step
        if abs(snapped - target) <= 0.3 * step:
            target, why = snapped, why + f", canal de {step / 1e3:g} kHz"
    return target - vfo, why
