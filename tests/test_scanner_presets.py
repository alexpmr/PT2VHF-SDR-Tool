import wave

import numpy as np

from pt2vhf.audio import ActivityRecorder
from pt2vhf.dsp.receiver import Receiver
from pt2vhf.engine import Engine
from pt2vhf.memory import MemoryBank
from pt2vhf.presets import PACKS, import_packs
from pt2vhf.scanner import SCAN_PRESETS, ScannerConfig, SpectrumScanner, detect_signals
from pt2vhf.sources.sim_sources import SimulatorSource


def test_presets_are_valid():
    for p in PACKS:
        assert p.channels
        for c in p.channels:
            assert 24_000 <= c.freq <= 1_766_000_000, c
            assert c.category == p.category or p.key == "ham"
    marine = {c.name: c.freq for c in next(p for p in PACKS if p.key == "marine").channels}
    assert marine["Marítimo 16"] == 156_800_000 and marine["Marítimo 67"] == 156_375_000
    px = [c.freq for c in next(p for p in PACKS if p.key == "px").channels]
    assert len(px) == 40 and px[0] == 26_965_000 and px[-1] == 27_405_000
    frs = {c.name: c.freq for c in next(p for p in PACKS if p.key == "frs").channels}
    assert frs["FRS 01"] == 462_562_500 and frs["FRS 08"] == 467_562_500 and frs["FRS 22"] == 462_725_000
    for r in SCAN_PRESETS:
        assert r.start < r.end


def test_import_packs_no_duplicates():
    bank = MemoryBank(None)
    bank.channels = []
    n1 = import_packs(bank, ["marine", "px"], favorite=True)
    n2 = import_packs(bank, ["marine", "px"])
    assert n1 == len(bank.channels) > 50 and n2 == 0
    assert all(c.favorite for c in bank.channels)
    assert len({c.id for c in bank.channels}) == len(bank.channels)


def test_detect_signals_synthetic():
    n, fs, center = 4096, 2.4e6, 146e6
    rng = np.random.default_rng(0)
    spec = rng.normal(-90, 1.5, n).astype(np.float32)
    freqs = center + (np.arange(n) - n / 2) * fs / n
    for f, w in ((145.57e6, 8000), (146.52e6, 6000)):
        spec[np.abs(freqs - f) < w] = -50
    spec[n // 2] = -20  # pico DC deve ser ignorado
    dets, floor = detect_signals(spec, center, fs, 144e6, 148e6, 5000, 10)
    assert abs(floor + 90) < 1
    assert sorted(d.freq for d in dets) == [145_570_000, 146_520_000]


def _engine():
    src = SimulatorSource(1_200_000, 145.5e6, realtime=False)
    e = Engine(None)
    e.source, e.rx = src, Receiver(src.sample_rate)
    e.tune(145.57e6)
    return e, src


def _run(e, src, sc, seconds):
    t, dur, evs = 0.0, src.block_size / src.sample_rate, []
    sc.start(t)
    for _ in range(int(seconds / dur)):
        e.process_block(src.generate(src.block_size))
        t += dur
        while e.wf_lines:
            spec, c, fs = e.wf_lines.popleft()
            evs += sc.feed(spec, c, fs, t)
    return evs


def test_scanner_discovers_simulated_band():
    e, src = _engine()
    sc = SpectrumScanner(e, ScannerConfig(144e6, 148e6))
    _run(e, src, sc, 20)
    found = sorted(round(h.freq) for h in sc.hits.values())
    for f in (145_250_000, 145_430_000, 145_570_000, 145_650_000, 145_800_000):
        assert f in found
    assert len(found) == 5  # nenhum falso positivo
    assert sc.sweeps >= 5 and e.hold_center


def test_scanner_listen_and_lockout():
    e, src = _engine()
    sc = SpectrumScanner(e, ScannerConfig(145.2e6, 145.9e6, listen=True, resume_s=1.0))
    sc.cfg.lockouts.update({145_250_000, 145_650_000, 145_800_000})
    evs = _run(e, src, sc, 12)
    listened = [ev[1] for ev in evs if ev[0] == "listen"]
    assert listened and listened[0] == 145_430_000
    assert not any(abs(f - 145.65e6) < 1000 for f in listened)
    assert any(ev[0] == "resume" for ev in evs)


def test_activity_recorder(tmp_path):
    rec = ActivityRecorder(str(tmp_path), 48_000, tail_s=0.5, min_s=0.5)
    blk = np.full(4800, 0.1, np.float32)
    evs = []
    for i in range(40):  # 2 s aberto, 2 s fechado
        evs.append(rec.process(blk if i < 20 else blk * 0, i < 20, 145.57e6, "NFM", -60))
    evs = [e for e in evs if e]
    assert len(evs) == 1 and abs(evs[0]["duration"] - 2.0) < 0.2
    with wave.open(evs[0]["file"]) as w:
        assert w.getframerate() == 48_000
    # transmissão curta demais é descartada
    for i in range(10):
        assert rec.process(blk, i < 2, 145.57e6, "NFM", -60) is None
    assert len(list(tmp_path.rglob("*.wav"))) == 1


def test_engine_auto_record_with_squelch(tmp_path):
    e, src = _engine()
    e.tune(145.430e6)
    e.rx.squelch.threshold_db = -60
    e.activity_rec = ActivityRecorder(str(tmp_path), 48_000, tail_s=1.0, min_s=1.0)
    dur = src.block_size / src.sample_rate
    for _ in range(int(12 / dur)):
        e.process_block(src.generate(src.block_size))
    acts = []
    while not e.events.empty():
        k, d, _ = e.events.get()
        if k == "activity":
            acts.append(d)
    assert acts and acts[0]["duration"] > 4  # a 'voz' simulada dura 7 s a cada 10 s
