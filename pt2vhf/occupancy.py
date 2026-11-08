"""Histórico de atividade RF por frequência e hora (janela móvel de 24 h).

Dados vêm de detecções reais do scanner, não de um medidor de ocupação
contínua do canal. Contamos no máximo uma detecção por minuto/frequência.
O cache local preserva o histórico entre execuções, sem serviços externos.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


BIN_HZ = 12_500
HOURS = 24


class OccupancyHistory:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else None
        self._hours: dict[int, dict[int, int]] = {}
        self._seen: set[tuple[int, int]] = set()
        self._dirty = False
        self._last_save = 0.0
        if self.path and self.path.exists():
            try:
                obj = json.loads(self.path.read_text(encoding="utf-8"))
                for hour, counts in obj.get("hours", {}).items():
                    self._hours[int(hour)] = {int(freq): int(n) for freq, n in counts.items() if int(n) > 0}
            except (OSError, ValueError, TypeError):
                self._hours.clear()
        self.prune()

    @staticmethod
    def hour_key(ts: float) -> int:
        return int(ts // 3600) * 3600

    @staticmethod
    def freq_bin(freq_hz: float) -> int:
        if not 24_000 <= freq_hz <= 2_000_000_000:
            raise ValueError("frequência inválida")
        return int(round(freq_hz / BIN_HZ) * BIN_HZ)

    def prune(self, now: float | None = None):
        now = time.time() if now is None else float(now)
        earliest = self.hour_key(now) - (HOURS - 1) * 3600
        for hour in list(self._hours):
            if hour < earliest or hour > self.hour_key(now):
                del self._hours[hour]
        self._seen = {p for p in self._seen if p[0] >= int(earliest // 60)}

    def record(self, freq_hz: float, ts: float | None = None) -> bool:
        ts = time.time() if ts is None else float(ts)
        self.prune(ts)
        bucket = self.freq_bin(freq_hz)
        minute = int(ts // 60)
        key = minute, bucket
        if key in self._seen:
            return False
        self._seen.add(key)
        hour = self.hour_key(ts)
        counts = self._hours.setdefault(hour, {})
        counts[bucket] = counts.get(bucket, 0) + 1
        self._dirty = True
        return True

    def matrix(self, now: float | None = None, limit: int = 80):
        now = time.time() if now is None else float(now)
        self.prune(now)
        end = self.hour_key(now)
        hours = [end - 3600 * i for i in range(HOURS - 1, -1, -1)]
        freqs = set()
        for hour in hours:
            freqs.update(self._hours.get(hour, {}))
        ranked = sorted(freqs, key=lambda f: (-sum(self._hours.get(h, {}).get(f, 0) for h in hours), f))
        return hours, [(f, [self._hours.get(hour, {}).get(f, 0) for hour in hours])
                       for f in ranked[:max(0, limit)]]

    def clear(self):
        self._hours.clear()
        self._seen.clear()
        self._dirty = True
        self.flush()

    def flush(self, force=False):
        if not self.path or (not self._dirty and not force):
            return
        now = time.time()
        if not force and now - self._last_save < 20:
            return
        self.prune(now)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"schema": 1, "bin_hz": BIN_HZ,
                "hours": {str(hour): {str(f): n for f, n in counts.items()}
                          for hour, counts in self._hours.items()}}
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)
        self._dirty = False
        self._last_save = now
