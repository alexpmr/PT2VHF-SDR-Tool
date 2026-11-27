"""v1.0.9: favoritos em menu suspenso por uso, Auto contínuo e zoom FFT do waterfall."""
from __future__ import annotations

import json

import numpy as np
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from pt2vhf.dsp.receiver import compute_spectrum
from pt2vhf.dsp.zoom import ZoomSpectrum, zoom_needed
from pt2vhf.memory import MemoryBank, MemoryChannel


# ----------------------------------------------------------------- favoritos
def test_favorites_sorted_by_use_and_old_json_still_loads(tmp_path):
    path = tmp_path / "memories.json"
    old = {"categories": ["Simplex"], "channels": [
        {"name": "A", "freq": 145.5e6, "favorite": True},
        {"name": "B", "freq": 146.5e6, "favorite": True},
        {"name": "C", "freq": 147.5e6, "favorite": False},
    ]}
    path.write_text(json.dumps(old), encoding="utf-8")
    bank = MemoryBank(path)
    assert [c.use_count for c in bank.channels] == [0, 0, 0]
    a, b, _c = bank.channels
    b.mark_used(now=10)
    b.mark_used(now=20)
    a.mark_used(now=30)
    assert [c.name for c in bank.favorites()] == ["B", "A"]
    bank.save()
    again = MemoryBank(path)
    assert [c.name for c in again.favorites()] == ["B", "A"]
    assert again.channels[1].use_count == 2 and again.channels[1].last_used == 20


def test_favorites_bar_is_a_dropdown(qt_lifecycle):
    from pt2vhf.ui.listening import FavoritesBar
    bar = FavoritesBar()
    chans = [MemoryChannel(f"F{i}", 144e6 + i * 25e3, favorite=True) for i in range(60)]
    chans[42].use_count = 9
    chans[7].use_count = 3
    bar.refresh(chans, current_freq=None)
    try:
        assert bar.combo.count() == 60
        assert bar.favorites()[0].name == "F42" and bar.favorites()[1].name == "F7"
        assert bar.combo.currentIndex() == -1
        got = []
        bar.recallRequested.connect(got.append)
        bar.mark_current(chans[7].freq)          # seleção sem disparar sintonia
        assert bar.combo.currentIndex() == 1 and got == []
        bar.combo.activated.emit(0)              # escolha do usuário
        assert got == [chans[42]]
        # cabe numa linha: altura de um combo, não uma fileira de teclas
        assert bar.sizeHint().height() < 46
    finally:
        bar.deleteLater()


# ----------------------------------------------------------------- zoom FFT
def _two_tones(fs, center, f1, f2, n_blocks=30, block=131072):
    n = 0
    for _ in range(n_blocks):
        k = np.arange(n, n + block)
        n += block
        iq = (0.1 * np.exp(2j * np.pi * (f1 - center) * k / fs)
              + 0.1 * np.exp(2j * np.pi * (f2 - center) * k / fs)
              + 1e-4 * (np.random.default_rng(n).standard_normal(block)
                        + 1j * np.random.default_rng(n + 1).standard_normal(block)))
        yield iq.astype(np.complex64)


def test_zoom_fft_resolves_what_the_native_fft_smears():
    fs, center = 2_400_000, 900_300_000
    f1, f2 = 900_000_000, 900_000_150   # 150 Hz: 2 bins nativos de 73 Hz
    assert zoom_needed(900_000_000, 10_000, center, fs, 32768)
    assert not zoom_needed(900_000_000, 500_000, center, fs, 32768)
    z = ZoomSpectrum(fs, center, 900_000_000, 10_000)
    last = None
    for blk in _two_tones(fs, center, f1, f2):
        z.feed(blk)
        last = blk
    spec = z.spectrum()
    assert spec is not None and z.fs_out / z.nfft < 10   # < 10 Hz por bin
    x = z.zoom_center + (np.arange(z.nfft) - z.nfft / 2) * z.fs_out / z.nfft
    view = np.abs(x - 900_000_075) < 400
    peaks = [i for i in np.flatnonzero(view)
             if spec[i] > spec[i - 1] and spec[i] >= spec[i + 1] and spec[i] > -40]
    assert len(peaks) == 2
    assert abs(x[peaks[0]] - f1) < 10 and abs(x[peaks[1]] - f2) < 10
    # FFT nativa 32768: os dois tons ficam a 2 bins, sem vale entre eles
    native = compute_spectrum(np.concatenate([last, last]), 32768, max_frames=2)
    xn = center + (np.arange(32768) - 16384) * fs / 32768
    nv = native[np.abs(xn - 900_000_075) < 400]
    assert z.fs_out / z.nfft * 7 < fs / 32768
    assert nv.max() - np.sort(nv)[-3] < 15


def test_zoom_fft_rejects_alias_outside_view():
    fs, center, zc = 2_400_000, 900_300_000, 900_000_000
    z = ZoomSpectrum(fs, center, zc, 10_000)
    off = fs / 8 + 1000            # cairia em +1 kHz sem o filtro do estágio 1
    n = 0
    for _ in range(30):
        k = np.arange(n, n + 131072)
        n += 131072
        z.feed(np.exp(2j * np.pi * (zc + off - center) * k / fs).astype(np.complex64))
    spec = z.spectrum()
    x = (np.arange(z.nfft) - z.nfft / 2) * z.fs_out / z.nfft
    assert spec[np.abs(x) < 5000].max() < -70


def test_engine_emits_zoom_lines_only_when_zoomed():
    from pt2vhf.engine import Engine
    eng = Engine()
    fs, center = 2_400_000, 900_300_000
    blk = next(_two_tones(fs, center, 900e6, 900.00015e6, n_blocks=1))
    assert eng._zoom_feed(blk, center, fs) is None
    eng.fft_size = 32768
    eng.zoom_view = (900e6, 10_000)
    z = eng._zoom_feed(blk, center, fs)
    assert z is not None and eng._zoom is z
    assert eng._zoom_feed(blk, center, fs) is z           # mesmo DDC entre blocos
    eng.zoom_view = (900e6 + 1000, 10_000)                 # pan pequeno: reaproveita
    assert eng._zoom_feed(blk, center, fs) is z
    eng.zoom_view = (900e6, 500_000)
    assert eng._zoom_feed(blk, center, fs) is None


def test_waterfall_renders_zoom_lines_at_screen_resolution(qt_lifecycle):
    from pt2vhf.ui.waterfall import SpectrumWaterfall
    w = SpectrumWaterfall()
    w.resize(1170, 780)
    w.show()
    QApplication.processEvents()
    fs, center, n = 2_400_000, 900_300_000, 32768
    views = []
    w.viewChanged.connect(lambda c, s: views.append((c, s)))
    try:
        w.add_line(np.full(n, -95.0, dtype=np.float32), center, fs)
        w.spec.setXRange(899.995, 900.005, padding=0)
        QApplication.processEvents()
        w._view_timer()
        assert views and abs(views[-1][1] - 10_000) < 1
        nz, zfs = 4096, 15_000.0
        z = np.full(nz, -110.0, dtype=np.float32)
        hz = (np.arange(nz) - nz / 2) * zfs / nz
        z[np.argmin(np.abs(hz))] = -20.0
        z[np.argmin(np.abs(hz - 150))] = -20.0
        w.add_zoom_line(z, 900_000_000, zfs, center, fs)
        assert w.zoom_active
        row = w._buf[0]
        assert row.size >= 256, "imagem acompanha a tela, não os ~137 bins nativos"
        hot = np.flatnonzero(row > -60)
        assert len(hot) >= 2 and hot.max() - hot.min() >= 8
        lo, hi = w.auto_levels()
        assert lo < -110, "Auto usa o espectro do zoom, não o nativo (-95 dB)"
        w.add_line(np.full(n, -95.0, dtype=np.float32), center, fs)  # zoom desligado
        assert not w.zoom_active
    finally:
        w.close()


# ----------------------------------------------------------------- Auto contínuo
def test_auto_levels_button_is_a_persistent_toggle(tmp_path, monkeypatch, qt_lifecycle):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from pt2vhf.ui.main_window import MainWindow
    app = QtWidgets.QApplication.instance()
    w = MainWindow()
    w.show()
    app.processEvents()
    try:
        assert w.wf_auto.isCheckable() and w.wf_auto.isChecked()   # padrão: ligado
        assert w._auto_levels_timer.isActive()
        w.wf.add_line(np.full(4096, -60.0, dtype=np.float32), 900e6, 2.4e6)
        w._auto_levels()
        assert w.wf_auto.isChecked(), "ajuste automático não pode desligar o próprio Auto"
        assert w.wf.min_db > -75, "piso acompanha o ruído (UHF não fica preto)"
        w.wf_min.setValue(w.wf_min.value() - 10)                    # ajuste manual
        assert not w.wf_auto.isChecked() and not w._auto_levels_timer.isActive()
        assert w.cfg["wf_auto_levels"] is False
        w.wf_auto.setChecked(True)
        assert w.cfg["wf_auto_levels"] is True and w._auto_levels_timer.isActive()
        # vista estreita liga o zoom FFT no engine; vista total desliga
        monkeypatch.setattr(type(w.engine), "sample_rate", property(lambda _self: 2_400_000))
        w._wf_view_changed(900e6, 10_000)
        assert w.engine.zoom_view == (900e6, 10_000)
        w._wf_view_changed(900e6, w.engine.sample_rate)
        assert w.engine.zoom_view is None
    finally:
        w.close()
