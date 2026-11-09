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
