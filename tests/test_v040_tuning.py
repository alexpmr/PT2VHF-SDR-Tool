import numpy as np

from pt2vhf.dsp.assist import fine_tune
from tests.synth_signals import FS, am, cw, noise, nfm, ssb240


def _shift(x, hz):
    return (x * np.exp(2j * np.pi * hz * np.arange(len(x)) / FS)).astype(np.complex64)


def test_fine_tune_am_cw_carrier_subbin():
    x = _shift(am(), 1234.0) + noise(FS, 0.01)
    d, why = fine_tune(x, FS, "AM", 121.5e6, step=0)
    assert abs(d - 1234) < 3 and "portadora" in why
    x = _shift(cw(), -387.0) + noise(FS, 0.01)
    d, _ = fine_tune(x, FS, "CW", 7.02e6)
    assert abs(d + 387) < 3


def test_fine_tune_nfm_snaps_to_channel():
    # transmissão em 145,575 MHz, mas o VFO ficou em 145,5716 (clique impreciso no waterfall)
    x = _shift(nfm(), 145.575e6 - 145.5716e6) + noise(FS, 0.01)
    d, why = fine_tune(x, FS, "NFM", 145.5716e6, step=12_500)
    assert abs(145.5716e6 + d - 145.575e6) < 1 and "canal" in why


def test_fine_tune_ssb_and_no_signal():
    x = ssb240(delta=180) + noise(2 * FS, 0.01)
    d, _ = fine_tune(x.astype(np.complex64), FS, "USB", 14.2e6)
    assert abs(d - 180) < 15
    assert fine_tune(noise(FS, 1).astype(np.complex64), FS, "NFM", 145e6) is None


def test_vox_preroll_and_single_file(tmp_path):
    import wave
    from pt2vhf.audio import ActivityRecorder
    rec = ActivityRecorder(str(tmp_path), 48_000, tail_s=0.5, min_s=0.5, preroll_s=0.5, single_file=True)
    quiet = np.full(4800, 0.01, np.float32)
    loud = np.full(4800, 0.3, np.float32)
    evs = []
    for _ in range(3):           # três transmissões de 1 s separadas por 2 s de silêncio
        for i in range(20):
            evs.append(rec.process(quiet, False, 145.57e6, "NFM", -100))
        for i in range(10):
            evs.append(rec.process(loud, True, 145.57e6, "NFM", -60))
    for i in range(10):
        evs.append(rec.process(quiet, False, 145.57e6, "NFM", -100))
    path = rec.session_path
    rec.close()
    evs = [e for e in evs if e]
    assert len(evs) == 3 and all(abs(e["duration"] - 1.0) < 0.15 for e in evs)
    assert len({e["file"] for e in evs}) == 1
    with wave.open(str(path)) as w:
        secs = w.getnframes() / 48_000
    assert 5.5 < secs < 6.5  # 3 × (0,5 pré + 1 s + 0,5 cauda); sem VOX seriam 12 s


def test_updater_select_and_kind(tmp_path):
    from pathlib import Path

    from pt2vhf import updater
    m = {"schema": 1, "product": "sdr", "status": "available", "version": "9.0.0", "notes": "n",
         "files": [{"kind": "portable", "name": "PT2VHF-SDR-Tool-v9.0.0-Win11-x64-Portable.exe",
                    "url": "https://www.pt2vhf.com/downloads/sdr-tool/PT2VHF-SDR-Tool-v9.0.0-Win11-x64-Portable.exe",
                    "size": 100, "sha256": "a" * 64},
                   {"kind": "installer", "name": "x.exe", "url": "https://evil.example/x.exe", "size": 100,
                    "sha256": "a" * 64}]}
    assert updater.select_update(m, "portable").file["kind"] == "portable"
    assert updater.select_update(m, "installer").file is None      # fora do www.pt2vhf.com: recusado
    assert updater.select_update({**m, "version": "0.0.1"}, "portable") is None
    try:
        updater.select_update({**m, "product": "sat"}, "portable")
        raise AssertionError
    except updater.UpdateError:
        pass
    assert updater.install_kind(frozen=False) == "source"
    assert updater.install_kind(Path(tmp_path / "PT2VHF-SDR-Tool-v0.4.0-Win11-x64-Portable.exe"), frozen=True) == "portable"
    assert updater.install_kind(Path(tmp_path / "PT2VHF-SDR-Tool.exe"), frozen=True) == "installer"
    (tmp_path / updater.RESULT_FILE).write_text("ok\n0.4.0\nAtualizado\n", encoding="utf-8")
    assert updater.read_update_result(tmp_path) == ("ok", "0.4.0", "Atualizado")
    assert updater.read_update_result(tmp_path) is None
