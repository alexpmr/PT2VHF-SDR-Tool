"""Logical RF frequency adapter for external, non-inverting upconverters.

Public frequencies (VFO, waterfall, scan, memories, CAT) remain on the antenna
RF scale. Only actual device tune/check commands are translated. This is NOT
the RTL-SDR Blog V4 internal HF conversion nor an oscillator PPM correction.
"""
from __future__ import annotations

import math


class FrequencyTranslatedSource:
    """Transparent source adapter; physical device frequency = RF + offset."""

    def __init__(self, source, offset_hz: float):
        offset = float(offset_hz)
        if not math.isfinite(offset) or abs(offset) > 1_500_000_000:
            raise ValueError("Offset do conversor externo inválido")
        if not source.tunable:
            raise ValueError("A fonte não permite sintonização por conversor externo")
        self._source = source
        self.offset_hz = offset

    @property
    def center_freq(self) -> float:
        return self._source.center_freq - self.offset_hz

    @property
    def hardware_center_freq(self) -> float:
        return self._source.center_freq

    def set_center_freq(self, rf_hz: float):
        return self._source.set_center_freq(float(rf_hz) + self.offset_hz)

    def check_freq(self, rf_hz: float) -> str:
        return self._source.check_freq(float(rf_hz) + self.offset_hz)

    def __getattr__(self, name: str):
        return getattr(self._source, name)
