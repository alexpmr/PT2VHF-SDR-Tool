from pt2vhf.dsp.receiver import Receiver
from pt2vhf.engine import Engine
from pt2vhf.memory import MemoryBank, MemoryChannel, band_for
from pt2vhf.sources.sim_sources import SimulatorSource


def test_band_plan():
    assert band_for(145.57e6).name == "2 m"
    assert band_for(98.1e6).name == "FM Broadcast"
    assert band_for(1e3) is None


def test_memory_save_load_and_csv(tmp_path):
    bank = MemoryBank(tmp_path / "m.json")
    n0 = len(bank.channels)
    bank.add(MemoryChannel("Rep teste", 146.79e6, "NFM", 12000, "Repetidoras", ctcss=88.5, offset=-600e3))
    bank.save()
    bank2 = MemoryBank(tmp_path / "m.json")
    assert len(bank2.channels) == n0 + 1
    csvp = tmp_path / "c.csv"
    bank2.export_csv(str(csvp))
    bank3 = MemoryBank(None)
    bank3.channels = []
    assert bank3.import_csv(str(csvp)) == n0 + 1
    rep = next(c for c in bank3.channels if c.name == "Rep teste")
    assert rep.ctcss == 88.5 and rep.offset == -600e3 and rep.category == "Repetidoras"


def _engine(fs=1_200_000):
    src = SimulatorSource(fs, 145.5e6, realtime=False)
    e = Engine(None)
    e.source = src
    e.rx = Receiver(fs)
    return e, src


def test_engine_end_to_end_aprs_dtmf_ctcss():
    e, src = _engine()
    e.tune(145.570e6)
    dur = src.block_size / src.sample_rate
    for _ in range(int(7 / dur)):
        e.process_block(src.generate(src.block_size))
    events = []
    while not e.events.empty():
        events.append(e.events.get())
    aprs = [d for k, d, _ in events if k == "aprs"]
    assert aprs and aprs[0].source == "PY2SIM-9"
    assert e.spectrum is not None and len(e.wf_lines) > 0

    e.tune(145.430e6)
    for _ in range(int(10 / dur)):
        e.process_block(src.generate(src.block_size))
    digits = []
    while not e.events.empty():
        k, d, _ = e.events.get()
        if k == "dtmf":
            digits.append(d)
    assert "".join(digits) == "1479#"
    assert e.status["ctcss"] == 88.5


def test_retune_moves_center_when_out_of_span():
    e, src = _engine()
    e.tune(145.570e6)
    e._retune(e.vfo, force=True)
    c0 = src.center_freq
    e.tune(146.9e6)
    assert src.center_freq != c0
    assert abs(e.rx.offset_hz) < src.sample_rate / 2
