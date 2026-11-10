"""WAV RIFF capacity and fail-closed IQ recorder lifecycle tests.

All samples and sources are synthetic. No claim of RF model accuracy.
"""
import json
import wave

import numpy as np
import pytest

from pt2vhf.audio import MAX_RIFF_DATA_BYTES, WavRecorder, WavSizeLimitError
from pt2vhf.iq_provenance import sidecar_path


def _iq(n):
    return np.full(n, 0.1 + 0.04j, dtype=np.complex64)


def _engine():
    from pt2vhf.engine import Engine
    from pt2vhf.dsp.receiver import Receiver

    class StubSource:
        center_freq = 145_500_000
        sample_rate = 240_000
        name = "SYNTHETIC"
        dropped = 0

    eng = Engine()
    eng.source = StubSource()
    eng.rx = Receiver(240_000)
    return eng


def test_riff_limit_is_below_u32_container_boundary():
    assert MAX_RIFF_DATA_BYTES < 0xFFFFFFFF - 36
    assert MAX_RIFF_DATA_BYTES > 4_000_000_000


def test_pcm16_iq_recorder_refuses_overflow_without_partial_write(tmp_path):
    path = tmp_path / "limited.wav"
    rec = WavRecorder(path, 240_000, 2)
    rec.max_data_bytes = 4096 * 4
    rec.write(_iq(4096))
    with pytest.raises(WavSizeLimitError, match="4 GiB"):
        rec.write(_iq(1))
    assert rec.samples == 4096
    rec.close()
    with wave.open(str(path), "rb") as wav:
        assert wav.getnframes() == 4096
        assert wav.getnchannels() == 2
        assert wav.getsampwidth() == 2


def test_pcm16_mono_recorder_rejects_before_first_write(tmp_path):
    rec = WavRecorder(tmp_path / "mono.wav", 48_000, 1)
    rec.max_data_bytes = 10
    with pytest.raises(WavSizeLimitError):
        rec.write(np.zeros(16, dtype=np.float32))
    assert rec.samples == 0
    rec.close()
    with wave.open(str(rec.path), "rb") as wav:
        assert wav.getnframes() == 0


def test_engine_limit_stops_recording_and_invalidates_sidecar(tmp_path):
    eng = _engine()
    wav_path = eng.start_iq_recording(str(tmp_path))
    with eng._lock:
        eng._iq_rec.max_data_bytes = 4 * 16384
    eng.process_block(_iq(16384))
    assert eng.recording_iq
    eng.process_block(_iq(16384))
    assert not eng.recording_iq
    report = json.loads(sidecar_path(wav_path).read_text(encoding="utf-8"))
    assert report["capture_state"] == "complete"
    assert not report["suitable_for_continuous_channelization"]
    assert "wav_riff_limit" in report["invalid_reasons"]
    assert report["written_frames"] == 16384
    assert any(event[0] == "iq_recording_warning" for event in list(eng.events.queue))
    with wave.open(str(wav_path), "rb") as wav:
        assert wav.getnframes() == 16384


def test_engine_disk_write_failure_is_not_treated_as_good_capture(tmp_path, monkeypatch):
    eng = _engine()
    path = eng.start_iq_recording(str(tmp_path))

    def fail_write(_samples):
        raise OSError("Synthetic disk full")

    monkeypatch.setattr(eng._iq_rec, "write", fail_write)
    eng.process_block(_iq(16384))
    assert not eng.recording_iq
    report = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert "wav_write_failed" in report["invalid_reasons"]
    assert not report["suitable_for_continuous_channelization"]


def test_engine_close_failure_keeps_pending_marker(tmp_path, monkeypatch):
    eng = _engine()
    path = eng.start_iq_recording(str(tmp_path))
    recorder = eng._iq_rec
    normal_close = recorder.close

    def fail_close():
        raise OSError("Synthetic close failure")

    monkeypatch.setattr(recorder, "close", fail_close)
    eng.stop_iq_recording()
    normal_close()
    assert not eng.recording_iq
    report = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert report["capture_state"] == "recording"
    assert not report["completed"]
    assert "capture_not_completed" in report["invalid_reasons"]
    assert any(event[0] == "iq_recording_warning" for event in list(eng.events.queue))


def test_engine_checksum_failure_keeps_pending_marker(tmp_path, monkeypatch):
    eng = _engine()
    path = eng.start_iq_recording(str(tmp_path))
    with eng._lock:
        eng._iq_rec.write(_iq(16384))
        eng._iq_provenance.observe(145_500_000, 240_000, 16384, True)
        metadata = eng._iq_provenance

    def fail_checksum(_frames):
        raise OSError("Synthetic checksum failure")

    monkeypatch.setattr(metadata, "final_report", fail_checksum)
    eng.stop_iq_recording()
    assert not eng.recording_iq
    assert path.exists()
    report = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert report["capture_state"] == "recording"
    assert not report["suitable_for_continuous_channelization"]
    assert any(event[0] == "iq_recording_warning" for event in list(eng.events.queue))
