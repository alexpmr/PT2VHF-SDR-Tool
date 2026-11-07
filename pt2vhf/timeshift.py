"""Voltar no tempo: buffer circular do IQ bruto da faixa inteira.

Guarda os últimos N segundos com 8 bits por componente (a resolução do próprio RTL-SDR),
mais a frequência central de cada trecho. Permite reouvir qualquer frequência da faixa gravada,
em qualquer modo, enquanto a recepção ao vivo continua.
"""
from __future__ import annotations

import numpy as np


class TimeShiftBuffer:
    def __init__(self, sample_rate: int, seconds: float):
        self.sample_rate = int(sample_rate)
        self.seconds = float(seconds)
        self.capacity = max(1, int(self.sample_rate * self.seconds))
        self._buf = np.zeros((self.capacity, 2), np.int8)
        self._centers: list[tuple[int, float]] = []  # (posição absoluta inicial, centro)
        self.written = 0                             # total de amostras escritas (absoluto)
        self.scale = 127.0

    @property
    def megabytes(self) -> float:
        return self._buf.nbytes / 1e6

    @property
    def available_seconds(self) -> float:
        return min(self.written, self.capacity) / self.sample_rate

    def append(self, iq: np.ndarray, center: float):
        n = len(iq)
        if n == 0:
            return
        if not self._centers or self._centers[-1][1] != center:
            self._centers.append((self.written, float(center)))
        q = np.empty((n, 2), np.int8)
        q[:, 0] = np.clip(np.round(iq.real * self.scale), -127, 127)
        q[:, 1] = np.clip(np.round(iq.imag * self.scale), -127, 127)
        if n >= self.capacity:
            q = q[-self.capacity:]
            start = self.written + n - self.capacity
            n = self.capacity
        else:
            start = self.written
        i = start % self.capacity
        first = min(n, self.capacity - i)
        self._buf[i:i + first] = q[:first]
        if first < n:
            self._buf[:n - first] = q[first:]
        self.written += len(iq)
        oldest = self.written - self.capacity
        while len(self._centers) > 1 and self._centers[1][0] <= oldest:
            self._centers.pop(0)

    def oldest(self) -> int:
        return max(0, self.written - self.capacity)

    def read(self, pos: int, n: int) -> tuple[np.ndarray, float] | None:
        """Lê n amostras a partir da posição absoluta `pos`. Retorna (iq, centro)."""
        pos = max(pos, self.oldest())
        n = min(n, self.written - pos)
        if n <= 0:
            return None
        i = pos % self.capacity
        first = min(n, self.capacity - i)
        raw = np.concatenate((self._buf[i:i + first], self._buf[:n - first])) if first < n else self._buf[i:i + n]
        iq = (raw[:, 0].astype(np.float32) + 1j * raw[:, 1].astype(np.float32)) / self.scale
        return iq.astype(np.complex64), self.center_at(pos)

    def center_at(self, pos: int) -> float:
        c = self._centers[0][1] if self._centers else 0.0
        for start, center in self._centers:
            if start <= pos:
                c = center
            else:
                break
        return c
