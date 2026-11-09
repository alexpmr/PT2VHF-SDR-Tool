"""Tests of IQ metadata and converter interlock; every signal is synthetic."""
import json
import wave
import numpy as np
import pytest

from pt2vhf.iq_provenance import IQCaptureProvenance, sidecar_path, write_sidecar
from scripts.prepare_iq_rf_capture import convert


def make_wav(path, n=24000):
    t=np.arange(n)/240000.
    z=.4*np.exp(2j*np.pi*1000*t)
    samples=np.empty(2*n,dtype="<i2")
    samples[::2]=np.round(z.real*32767).astype("<i2")
    samples[1::2]=np.round(z.imag*32767).astype("<i2")
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(240000)
        w.writeframes(samples.tobytes())


def metadata(path, count=24000, vox=False):
    m=IQCaptureProvenance(path,center_hz=145500000,sample_rate=240000,
                           vfo_hz=145501000,source="SYNTHETIC",mode="NFM",vox=vox)
    m.observe(145500000,240000,count,True)
    return m


def test_stable_sidecar(tmp_path):
    wav=tmp_path/"raw.wav";make_wav(wav)
    r=metadata(wav).report(24000)
    assert r["suitable_for_continuous_channelization"]
    assert r["rf_provenance_verified"] is False
    write_sidecar(wav,r)
    saved=json.loads(sidecar_path(wav).read_text())
    assert saved["wav_name"]=="raw.wav"
    assert saved["written_frames"]==24000


def test_center_and_rate_changes_invalid(tmp_path):
    m=metadata(tmp_path/"a.wav",4096)
    m.observe(145520000,192000,4096,True)
    r=m.report(8191)
    assert r["center_change_count"]==1
    assert r["center_change_events"][0]["recorded_frame_offset"]==4096
    assert {"center_frequency_changed","sample_rate_changed",
            "wav_frame_count_mismatch"}.issubset(set(r["invalid_reasons"]))


def test_vox_skip_is_invalid(tmp_path):
    m=metadata(tmp_path/"a.wav",4096,True)
    m.observe(145500000,240000,2048,False)
    r=m.report(4096)
    assert "vox_gated_iq" in r["invalid_reasons"]
    assert r["blocks_skipped"]==1


def test_converter_accepts_valid_sidecar_center(tmp_path):
    src,dst=tmp_path/"raw.wav",tmp_path/"channel.wav"
    make_wav(src)
    write_sidecar(src,metadata(src).report(24000))
    result=convert(src,dst,None,145501000)
    assert result["capture_metadata_checked"]
    assert result["center_hz"]==145500000
    with wave.open(str(dst),"rb") as w:
        assert w.getframerate()==48000 and w.getnframes()==4800


def test_converter_rejects_conflicting_center(tmp_path):
    src,dst=tmp_path/"raw.wav",tmp_path/"channel.wav"
    make_wav(src)
    write_sidecar(src,metadata(src).report(24000))
    with pytest.raises(ValueError,match="Requested center"):
        convert(src,dst,145502000,145501000)
    assert not dst.exists()


@pytest.mark.parametrize("condition",["vox","changed_center","incorrect_frames","incomplete"])
def test_converter_rejects_invalid_sidecar(tmp_path,condition):
    src,dst=tmp_path/"raw.wav",tmp_path/"channel.wav"
    make_wav(src)
    r=metadata(src,vox=condition=="vox").report(24000)
    if condition=="changed_center":
        r["center_change_count"]=1
        r["invalid_reasons"]=["center_frequency_changed"]
        r["suitable_for_continuous_channelization"]=False
    if condition=="incorrect_frames":r["written_frames"]=12000
    if condition=="incomplete":r["completed"]=False
    write_sidecar(src,r)
    with pytest.raises(ValueError,match="sidecar|VOX|rate|sample"):
        convert(src,dst,145500000,145501000)
    assert not dst.exists()


def test_legacy_wav_requires_manual_center(tmp_path):
    src,dst=tmp_path/"raw.wav",tmp_path/"channel.wav"
    make_wav(src)
    with pytest.raises(ValueError,match="Missing --center-hz"):
        convert(src,dst,None,145501000)
    assert not convert(src,dst,145500000,145501000)["capture_metadata_checked"]


def test_engine_stop_finalizes_sidecar(tmp_path):
    from pt2vhf.engine import Engine
    from pt2vhf.dsp.receiver import Receiver
    class Source:
        center_freq=145500000
        sample_rate=240000
        name="SYNTHETIC"
    engine=Engine()
    engine.source=Source()
    engine.rx=Receiver(240000)
    wav=engine.start_iq_recording(str(tmp_path))
    with engine._lock:
        engine._iq_rec.write(np.full(4096,.1+0j,dtype=np.complex64))
        engine._iq_provenance.observe(145500000,240000,4096,True)
    engine.stop_iq_recording()
    sidecar=json.loads(sidecar_path(wav).read_text())
    assert sidecar["written_frames"]==4096
    assert sidecar["suitable_for_continuous_channelization"]

def test_pending_marker_exists_before_iq_data(tmp_path):
    from pt2vhf.engine import Engine
    from pt2vhf.dsp.receiver import Receiver

    class Source:
        center_freq = 145500000
        sample_rate = 240000
        name = "SYNTHETIC"

    engine = Engine()
    engine.source = Source()
    engine.rx = Receiver(240000)
    path = engine.start_iq_recording(str(tmp_path))
    marker = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert marker["schema_version"] == 2
    assert marker["capture_state"] == "recording"
    assert marker["completed"] is False
    assert marker["suitable_for_continuous_channelization"] is False
    assert "capture_not_completed" in marker["invalid_reasons"]
    assert marker["wav_sha256"] is None
    engine.stop_iq_recording()
    finished = json.loads(sidecar_path(path).read_text(encoding="utf-8"))
    assert finished["capture_state"] == "complete"
    assert finished["completed"] is True
    assert finished["wav_sha256"] is not None
    assert not finished["suitable_for_continuous_channelization"]


def test_new_capture_integrity_and_actual_sha256(tmp_path):
    from pt2vhf.iq_provenance import sha256_file

    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    completed = metadata(source).final_report(24000)
    assert completed["schema_version"] == 2
    assert completed["wav_sha256"] == sha256_file(source)
    assert completed["wav_size_bytes"] == source.stat().st_size
    write_sidecar(source, completed)
    converted = convert(source, dest, None, 145501000)
    assert converted["capture_integrity_verified"] is True
    assert converted["capture_metadata_checked"] is True
    assert converted["provenance_verified"] is False


def test_changed_payload_with_same_file_size_is_rejected(tmp_path):
    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    write_sidecar(source, metadata(source).final_report(24000))
    with source.open("r+b") as f:
        f.seek(100)
        original = f.read(1)
        f.seek(100)
        f.write(bytes([original[0] ^ 0x80]))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        convert(source, dest, None, 145501000)
    assert not dest.exists()


def test_changed_file_length_is_rejected(tmp_path):
    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    write_sidecar(source, metadata(source).final_report(24000))
    with source.open("ab") as f:
        f.write(b"padding")
    with pytest.raises(ValueError, match="file size"):
        convert(source, dest, None, 145501000)
    assert not dest.exists()


@pytest.mark.parametrize("bad", ["missing_sha", "invalid_sha", "missing_size", "missing_complete"])
def test_corrupted_completed_sidecar_fails_closed(tmp_path, bad):
    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    report = metadata(source).final_report(24000)
    if bad == "missing_sha":
        report.pop("wav_sha256")
    elif bad == "invalid_sha":
        report["wav_sha256"] = "G" * 64
    elif bad == "missing_size":
        report.pop("wav_size_bytes")
    else:
        report["capture_state"] = "recording"
    write_sidecar(source, report)
    with pytest.raises(ValueError, match="SHA-256|file size"):
        convert(source, dest, None, 145501000)
    assert not dest.exists()


def test_incomplete_capture_never_falls_back_to_legacy_mode(tmp_path):
    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    write_sidecar(source, metadata(source).pending_report())
    with pytest.raises(ValueError, match="Invalid/incomplete"):
        convert(source, dest, 145500000, 145501000)
    assert not dest.exists()


def test_legacy_sidecar_allowed_but_integrity_unverified(tmp_path):
    source, dest = tmp_path / "source.wav", tmp_path / "channel.wav"
    make_wav(source)
    write_sidecar(source, metadata(source).report(24000))
    result = convert(source, dest, None, 145501000)
    assert result["capture_metadata_checked"]
    assert result["capture_integrity_verified"] is False


def test_engine_collision_does_not_overwrite_iq(tmp_path):
    from pt2vhf.engine import Engine
    from pt2vhf.dsp.receiver import Receiver

    class Source:
        center_freq = 145500000
        sample_rate = 240000
        name = "SYNTHETIC"

    engine = Engine()
    engine.source = Source()
    engine.rx = Receiver(240000)
    first = engine.start_iq_recording(str(tmp_path))
    with engine._lock:
        engine._iq_rec.write(np.full(4096, .1+0j, dtype=np.complex64))
        engine._iq_provenance.observe(145500000, 240000, 4096, True)
    engine.stop_iq_recording()
    original_content = first.read_bytes()
    second = engine.start_iq_recording(str(tmp_path))
    assert second != first
    engine.stop_iq_recording()
    assert first.read_bytes() == original_content
