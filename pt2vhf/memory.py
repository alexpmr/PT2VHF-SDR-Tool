"""Memórias de canais com categorias, plano de bandas e importação/exportação CSV (CHIRP)."""
from __future__ import annotations

import csv
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Band:
    name: str
    start: float
    end: float
    mode: str
    step: int
    service: str = "Radioamador"


# Plano de bandas (IARU Região 2 / Anatel - referência rápida).
BAND_PLAN = [
    Band("160 m", 1.8e6, 2.0e6, "LSB", 100),
    Band("80 m", 3.5e6, 4.0e6, "LSB", 100),
    Band("40 m", 7.0e6, 7.3e6, "LSB", 100),
    Band("30 m", 10.1e6, 10.15e6, "USB", 100),
    Band("20 m", 14.0e6, 14.35e6, "USB", 100),
    Band("17 m", 18.068e6, 18.168e6, "USB", 100),
    Band("15 m", 21.0e6, 21.45e6, "USB", 100),
    Band("12 m", 24.89e6, 24.99e6, "USB", 100),
    Band("11 m (PX)", 26.965e6, 27.405e6, "AM", 10000, "Faixa do Cidadão"),
    Band("10 m", 28.0e6, 29.7e6, "USB", 100),
    Band("6 m", 50.0e6, 54.0e6, "USB", 1000),
    Band("FM Broadcast", 76.0e6, 108.0e6, "WFM", 100000, "Radiodifusão"),
    Band("Aviação (VHF)", 108.0e6, 137.0e6, "AM", 8333, "Aeronáutico"),
    Band("Satélites meteo", 137.0e6, 138.0e6, "WFM", 1000, "Satélite"),
    Band("2 m", 144.0e6, 148.0e6, "NFM", 5000),
    Band("Marítimo VHF", 156.0e6, 162.05e6, "NFM", 25000, "Marítimo"),
    Band("1,25 m", 220.0e6, 225.0e6, "NFM", 5000),
    Band("70 cm", 430.0e6, 440.0e6, "NFM", 12500),
    Band("PMR/Uso livre", 462.5e6, 467.75e6, "NFM", 12500, "Rádio comunicador"),
    Band("23 cm", 1240.0e6, 1300.0e6, "NFM", 25000),
]


def band_for(freq: float) -> Band | None:
    for b in BAND_PLAN:
        if b.start <= freq <= b.end:
            return b
    return None


DEFAULT_CATEGORIES = [
    "Repetidoras", "Simplex", "APRS / Digital", "Satélites", "Aviação",
    "Marítimo", "Broadcast", "Utilidades", "Favoritos",
]


@dataclass
class MemoryChannel:
    name: str
    freq: float
    mode: str = "NFM"
    bandwidth: float = 12000.0
    category: str = "Simplex"
    squelch: float | None = None
    ctcss: float | None = None
    offset: float = 0.0          # deslocamento de repetidora (informativo)
    notes: str = ""
    favorite: bool = False
    skip_scan: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    @property
    def band(self) -> str:
        b = band_for(self.freq)
        return b.name if b else "Fora de banda"


def default_memories() -> list[MemoryChannel]:
    """Exemplos iniciais (edite/importe as repetidoras da sua região)."""
    M = MemoryChannel
    return [
        M("APRS Brasil", 145.570e6, "NFM", 12000, "APRS / Digital", notes="Frequência APRS nacional"),
        M("ISS APRS/Digi", 145.825e6, "NFM", 12000, "Satélites", notes="ARISS packet"),
        M("ISS Voz (down)", 145.800e6, "NFM", 12000, "Satélites"),
        M("Chamada 2m FM", 146.520e6, "NFM", 12000, "Simplex", notes="Simplex de chamada IARU R2"),
        M("Chamada 70cm FM", 446.000e6, "NFM", 12000, "Simplex"),
        M("Emergência Aérea", 121.500e6, "AM", 8000, "Aviação"),
        M("Canal 16 (Marítimo)", 156.800e6, "NFM", 12000, "Marítimo", notes="Socorro e chamada"),
        M("NOAA/Meteor 137.1", 137.100e6, "WFM", 40000, "Satélites"),
        M("FM 98.1", 98.1e6, "WFM", 180000, "Broadcast"),
        M("40m SSB", 7.100e6, "LSB", 2700, "Simplex"),
        # Sinais do simulador (demonstração)
        M("SIM Voz + CTCSS", 145.430e6, "NFM", 12000, "Repetidoras", ctcss=88.5, notes="Simulador"),
        M("SIM Baliza CW", 145.800e6, "CW", 500, "Utilidades", notes="Simulador"),
        M("SIM AM 1 kHz", 145.650e6, "AM", 6000, "Utilidades", notes="Simulador"),
        M("SIM USB 2 tons", 145.250e6, "USB", 2700, "Utilidades", notes="Simulador"),
    ]


class MemoryBank:
    def __init__(self, path: Path | None = None):
        self.path = path
        self.channels: list[MemoryChannel] = []
        self.categories: list[str] = list(DEFAULT_CATEGORIES)
        if path and path.exists():
            self.load()
        else:
            self.channels = default_memories()

    # -------------------------------------------------------- persistência
    def load(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.categories = data.get("categories", list(DEFAULT_CATEGORIES))
        fields = MemoryChannel.__dataclass_fields__
        self.channels = [MemoryChannel(**{k: v for k, v in c.items() if k in fields})
                         for c in data.get("channels", [])]

    def save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"categories": self.categories, "channels": [asdict(c) for c in self.channels]}
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # -------------------------------------------------------- operações
    def add(self, ch: MemoryChannel):
        if ch.category not in self.categories:
            self.categories.append(ch.category)
        self.channels.append(ch)

    def remove(self, ch_id: str):
        self.channels = [c for c in self.channels if c.id != ch_id]

    def get(self, ch_id: str) -> MemoryChannel | None:
        return next((c for c in self.channels if c.id == ch_id), None)

    def by_category(self, cat: str) -> list[MemoryChannel]:
        return sorted((c for c in self.channels if c.category == cat), key=lambda c: c.freq)

    def in_range(self, f0: float, f1: float) -> list[MemoryChannel]:
        return [c for c in self.channels if f0 <= c.freq <= f1]

    # -------------------------------------------------------- CSV (CHIRP)
    CHIRP_FIELDS = ["Location", "Name", "Frequency", "Duplex", "Offset", "Tone", "rToneFreq",
                    "cToneFreq", "DtcsCode", "DtcsPolarity", "Mode", "TStep", "Skip", "Comment"]

    def export_csv(self, path: str, channels: list[MemoryChannel] | None = None):
        """Exporta no formato CSV do CHIRP (com coluna extra 'Category')."""
        chans = channels if channels is not None else self.channels
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self.CHIRP_FIELDS + ["Category"])
            w.writeheader()
            for i, c in enumerate(chans):
                mode = {"NFM": "NFM" if c.bandwidth < 9000 else "FM", "WFM": "WFM"}.get(c.mode, c.mode)
                duplex = "+" if c.offset > 0 else "-" if c.offset < 0 else ""
                w.writerow({
                    "Location": i, "Name": c.name[:16], "Frequency": f"{c.freq / 1e6:.6f}",
                    "Duplex": duplex, "Offset": f"{abs(c.offset) / 1e6:.6f}",
                    "Tone": "Tone" if c.ctcss else "", "rToneFreq": c.ctcss or 88.5,
                    "cToneFreq": c.ctcss or 88.5, "DtcsCode": "023", "DtcsPolarity": "NN",
                    "Mode": mode, "TStep": "5.00", "Skip": "S" if c.skip_scan else "",
                    "Comment": c.notes, "Category": c.category,
                })

    def import_csv(self, path: str, category: str | None = None) -> int:
        """Importa CSV do CHIRP (ou exportado por este programa). Retorna nº de canais."""
        n = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    freq = float(row.get("Frequency", "0")) * 1e6
                except ValueError:
                    continue
                if freq <= 0:
                    continue
                mode = (row.get("Mode") or "FM").upper()
                bw = 12000.0
                if mode == "FM":
                    mode = "NFM"
                elif mode == "NFM":
                    bw = 8000.0
                elif mode == "WFM":
                    bw = 180000.0
                elif mode == "AM":
                    bw = 8000.0
                elif mode in ("USB", "LSB"):
                    bw = 2700.0
                elif mode == "CW":
                    bw = 500.0
                else:
                    mode = "NFM"
                tone = None
                if (row.get("Tone") or "") in ("Tone", "TSQL"):
                    try:
                        tone = float(row.get("rToneFreq") or row.get("cToneFreq"))
                    except (TypeError, ValueError):
                        tone = None
                off = 0.0
                try:
                    o = float(row.get("Offset") or 0) * 1e6
                    off = o if row.get("Duplex") == "+" else -o if row.get("Duplex") == "-" else 0.0
                except ValueError:
                    pass
                cat = category or row.get("Category") or ("Repetidoras" if off else "Simplex")
                self.add(MemoryChannel(
                    name=row.get("Name") or f"{freq / 1e6:.4f}", freq=freq, mode=mode,
                    bandwidth=bw, category=cat, ctcss=tone, offset=off,
                    notes=row.get("Comment") or "", skip_scan=(row.get("Skip") == "S")))
                n += 1
        return n
