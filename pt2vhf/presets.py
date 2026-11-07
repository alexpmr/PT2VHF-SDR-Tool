"""Pacotes de memórias prontas (frequências padronizadas, válidas em qualquer região).

Frequências locais (torre/solo de aeroportos, repetidoras, rádios FM) dependem da cidade:
use o Scanner para descobri-las e salve como memória.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .memory import MemoryChannel


@dataclass
class PresetPack:
    key: str
    name: str
    category: str
    description: str
    channels: list[MemoryChannel] = field(default_factory=list)


def _ch(name, mhz, mode, bw, cat, notes=""):
    return MemoryChannel(name=name, freq=round(mhz * 1e6), mode=mode, bandwidth=bw, category=cat, notes=notes)


def _marine() -> list[MemoryChannel]:
    cat = "Marítimo"
    simplex = {
        6: "Segurança entre embarcações", 8: "Entre embarcações", 9: "Chamada / marinas",
        10: "Entre embarcações / operações", 12: "Operações portuárias", 13: "Navegação ponte a ponte",
        14: "Operações portuárias", 15: "Bordo (baixa potência)", 16: "SOCORRO E CHAMADA",
        17: "Bordo (baixa potência)", 67: "Entre embarcações", 68: "Operações portuárias / marinas",
        69: "Entre embarcações / portos", 71: "Operações portuárias", 72: "Entre embarcações",
        73: "Entre embarcações / portos", 77: "Entre embarcações",
    }
    out = []
    for n, desc in simplex.items():
        mhz = 156.000 + 0.050 * n if n < 60 else 156.025 + 0.050 * (n - 60)
        out.append(_ch(f"Marítimo {n:02d}", mhz, "NFM", 12000, cat, desc))
    out.append(_ch("Marítimo 70 (DSC)", 156.525, "NFM", 12000, cat, "Chamada seletiva digital (dados)"))
    out.append(_ch("AIS 1", 161.975, "NFM", 16000, cat, "Dados AIS (GMSK 9600)"))
    out.append(_ch("AIS 2", 162.025, "NFM", 16000, cat, "Dados AIS (GMSK 9600)"))
    return out


def _px() -> list[MemoryChannel]:
    # canais 1..40 (inclui o 'salto' clássico dos canais 3A/7A/11A/15A/19A e a inversão 23/24/25)
    freqs = [26.965, 26.975, 26.985, 27.005, 27.015, 27.025, 27.035, 27.055, 27.065, 27.075,
             27.085, 27.105, 27.115, 27.125, 27.135, 27.155, 27.165, 27.175, 27.185, 27.205,
             27.215, 27.225, 27.255, 27.235, 27.245]
    freqs += [27.265 + 0.010 * k for k in range(15)]  # 26..40
    notes = {9: "Emergência", 19: "Rodovias / caminhoneiros"}
    return [_ch(f"PX {i:02d}", f, "AM", 8000, "PX (11 m)", notes.get(i, "")) for i, f in enumerate(freqs, 1)]


def _frs_pmr() -> list[MemoryChannel]:
    cat = "Rádio comunicador"
    out = []
    for n in range(1, 23):
        if n <= 7:
            f = 462.5625 + 0.025 * (n - 1)
        elif n <= 14:
            f = 467.5625 + 0.025 * (n - 8)
        else:
            f = 462.5500 + 0.025 * (n - 15)
        out.append(_ch(f"FRS {n:02d}", f, "NFM", 12000, cat, "Uso livre (462/467 MHz)"))
    for n in range(1, 17):
        out.append(_ch(f"PMR446 {n:02d}", 446.00625 + 0.0125 * (n - 1), "NFM", 8000, cat, "PMR446"))
    return out


def _ham_calling() -> list[MemoryChannel]:
    c = "Radioamador"
    return [
        _ch("APRS Brasil", 145.570, "NFM", 12000, "APRS / Digital", "APRS nacional (AFSK 1200)"),
        _ch("Chamada FM 2 m", 146.520, "NFM", 12000, c, "Simplex de chamada FM (IARU R2)"),
        _ch("Chamada FM 70 cm", 446.000, "NFM", 12000, c, "Simplex de chamada FM"),
        _ch("Chamada SSB 2 m", 144.200, "USB", 2700, c, "Fracos sinais / SSB"),
        _ch("Chamada SSB 70 cm", 432.100, "USB", 2700, c, "Fracos sinais / SSB"),
        _ch("Chamada SSB 6 m", 50.125, "USB", 2700, c, "Banda mágica"),
        _ch("Fonia 80 m", 3.700, "LSB", 2700, c, "Região de fonia (ajuste fino)"),
        _ch("Fonia 40 m", 7.150, "LSB", 2700, c, "Região de fonia (ajuste fino)"),
        _ch("Fonia 20 m", 14.200, "USB", 2700, c, "Região de fonia (ajuste fino)"),
        _ch("Fonia 15 m", 21.300, "USB", 2700, c, "Região de fonia (ajuste fino)"),
        _ch("Fonia 10 m", 28.500, "USB", 2700, c, "Região de fonia (ajuste fino)"),
    ]


def _ham_digital() -> list[MemoryChannel]:
    c = "APRS / Digital"
    out = []
    for band, f in (("160 m", 1.840), ("80 m", 3.573), ("40 m", 7.074), ("30 m", 10.136), ("20 m", 14.074),
                    ("17 m", 18.100), ("15 m", 21.074), ("12 m", 24.915), ("10 m", 28.074), ("6 m", 50.313),
                    ("2 m", 144.174)):
        out.append(_ch(f"FT8 {band}", f, "USB", 3000, c, "Frequência de discagem FT8"))
    for band, f in (("40 m", 7.0475), ("20 m", 14.080), ("15 m", 21.140), ("10 m", 28.180)):
        out.append(_ch(f"FT4 {band}", f, "USB", 3000, c, "Frequência de discagem FT4"))
    for band, f in (("40 m", 7.0386), ("30 m", 10.1387), ("20 m", 14.0956)):
        out.append(_ch(f"WSPR {band}", f, "USB", 3000, c, "Balizas WSPR"))
    return out


def _satellites() -> list[MemoryChannel]:
    c = "Satélites"
    return [
        _ch("ISS Voz / SSTV", 145.800, "NFM", 16000, c, "Downlink da ISS (corrigir Doppler ±3,5 kHz)"),
        _ch("ISS APRS / Digi", 145.825, "NFM", 16000, c, "Digipeater APRS da ISS"),
        _ch("ISS Repetidora UHF", 437.800, "NFM", 16000, c, "Downlink da repetidora (Doppler ±10 kHz)"),
        _ch("SO-50 downlink", 436.795, "NFM", 16000, c, "Satélite FM (Doppler ±10 kHz)"),
    ]


def _aviation() -> list[MemoryChannel]:
    c = "Aviação"
    return [
        _ch("Emergência aérea", 121.500, "AM", 8000, c, "Guarda internacional"),
        _ch("Ar-ar", 123.450, "AM", 8000, c, "Comunicação entre aeronaves"),
        _ch("Emergência militar", 243.000, "AM", 8000, c, "Guarda UHF"),
        _ch("ACARS 131.550", 131.550, "AM", 8000, c, "Dados ACARS"),
    ]


def _time_signals() -> list[MemoryChannel]:
    c = "Utilidades"
    out = [_ch(f"WWV {f:g} MHz", f, "AM", 6000, c, "Sinal horário (EUA)") for f in (2.5, 5.0, 10.0, 15.0, 20.0)]
    out += [_ch(f"CHU {f:g} MHz", f, "AM", 6000, c, "Sinal horário (Canadá)") for f in (3.330, 7.850, 14.670)]
    return out


PACKS: list[PresetPack] = [
    PresetPack("ham", "Radioamador: chamada e fonia", "Radioamador",
               "Frequências de chamada FM/SSB em VHF/UHF e regiões de fonia em HF.", _ham_calling()),
    PresetPack("digital", "Radioamador: modos digitais (FT8/FT4/WSPR)", "APRS / Digital",
               "Frequências de discagem dos modos digitais de HF e VHF.", _ham_digital()),
    PresetPack("sat", "Satélites e ISS", "Satélites",
               "Downlinks da ISS e de satélite FM de radioamador.", _satellites()),
    PresetPack("air", "Aviação: frequências gerais", "Aviação",
               "Emergência, ar-ar, guarda militar e ACARS. Torre/solo/aproximação do seu aeroporto: "
               "use o Scanner em 118–137 MHz.", _aviation()),
    PresetPack("marine", "Marítimo VHF", "Marítimo",
               "Canais simplex internacionais (16 = socorro e chamada), DSC e AIS.", _marine()),
    PresetPack("px", "PX – Faixa do Cidadão (11 m)", "PX (11 m)",
               "Os 40 canais do PX (canal 9 emergência, 19 rodovias).", _px()),
    PresetPack("frs", "Rádio comunicador (FRS e PMR446)", "Rádio comunicador",
               "Canais de uso livre dos rádios comunicadores (walkie-talkies).", _frs_pmr()),
    PresetPack("time", "Sinais horários (HF)", "Utilidades",
               "WWV e CHU: referências de tempo e de propagação em ondas curtas.", _time_signals()),
]


def import_packs(bank, keys: list[str], favorite: bool = False) -> int:
    """Adiciona os pacotes ao banco, sem duplicar (mesma frequência e categoria). Retorna nº de canais novos."""
    added = 0
    existing = {(c.category, round(c.freq / 100)) for c in bank.channels}
    for pack in PACKS:
        if pack.key not in keys:
            continue
        for ch in pack.channels:
            key = (ch.category, round(ch.freq / 100))
            if key in existing:
                continue
            new = MemoryChannel(**{**ch.__dict__, "id": MemoryChannel(name="", freq=0).id})
            new.favorite = favorite
            bank.add(new)
            existing.add(key)
            added += 1
    return added
