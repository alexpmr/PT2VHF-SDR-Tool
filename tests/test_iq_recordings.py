"""Offline IQ WAV evaluation tests; test fixtures are synthetic, NOT RF."""
import json
import wave
import numpy as np
import pytest
from pt2vhf.dsp.iq_classifier import CLASSES, Classification
from scripts.evaluate_iq_recordings import read_manifest, read_windows, evaluate


def make_wav(path, rate=48000, channels=2):
    n=8192
    carrier=np.sin(2*np.pi*1100*np.arange(n)/rate)
    pcm=(14000*carrier).astype("<i2")
    if channels==2:
        pcm=np.stack((pcm,pcm//2),axis=1)
    with wave.open(str(path),"wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(pcm.tobytes())


def manifest(root, filename="a.wav", label="AM"):
    file=root/"manifest.json"
    file.write_text(json.dumps({"recordings":[
        {"path":filename,"mode":label,"session_id":"private-session-1",
         "device":"fake SDR","frequency_hz":145650000}]}))
    return file


def test_stereo_wav_windows_non_overlapping(tmp_path):
    f=tmp_path/"a.wav"
    make_wav(f)
    chunks=list(read_windows(f))
    assert len(chunks)==4
    assert all(c.shape==(2048,) and c.dtype==np.complex64 for c in chunks)


def test_manifest_blocks_traversal_and_wfm(tmp_path):
    make_wav(tmp_path/"a.wav")
    with pytest.raises(ValueError,match="leaves recordings root"):
        read_manifest(manifest(tmp_path,"../escape.wav"),tmp_path)
    with pytest.raises(ValueError,match="WFM"):
        read_manifest(manifest(tmp_path,label="WFM"),tmp_path)


@pytest.mark.parametrize("rate,channels",[(44100,2),(48000,1)])
def test_wav_format_rejection(tmp_path,rate,channels):
    wav=tmp_path/"bad.wav"
    make_wav(wav,rate=rate,channels=channels)
    with pytest.raises(ValueError,match="stereo PCM16"):
        list(read_windows(wav))


def test_aggregate_report_does_not_expose_session_names(tmp_path):
    make_wav(tmp_path/"a.wav")
    class Stub:
        def predict(self,iq):
            return Classification("AM",0.99,{k:(1 if k=="AM" else 0) for k in CLASSES})
    report=evaluate(manifest(tmp_path),tmp_path,Stub())
    assert report["sample_windows"]==4
    assert report["sessions"]==1
    assert report["accuracy_top1"]==1
    assert report["session_macro_accuracy"]==1
    assert "private-session-1" not in json.dumps(report)



def test_manifest_rejects_duplicate_recordings(tmp_path):
    make_wav(tmp_path/"a.wav")
    m=manifest(tmp_path)
    data=json.loads(m.read_text())
    data["recordings"].append(dict(data["recordings"][0], session_id="other-session"))
    m.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="Duplicate WAV"):
        read_manifest(m,tmp_path)


def test_manifest_rejects_session_crossing_devices(tmp_path):
    make_wav(tmp_path/"a.wav")
    make_wav(tmp_path/"b.wav")
    m=manifest(tmp_path)
    data=json.loads(m.read_text())
    data["recordings"].append(dict(data["recordings"][0],path="b.wav",device="different SDR"))
    m.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="session_id cannot span"):
        read_manifest(m,tmp_path)


@pytest.mark.parametrize("frequency",[float("nan"),float("inf"),-5])
def test_manifest_rejects_invalid_frequency(tmp_path,frequency):
    make_wav(tmp_path/"a.wav")
    m=manifest(tmp_path)
    data=json.loads(m.read_text())
    data["recordings"][0]["frequency_hz"]=frequency
    m.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="Invalid frequency"):
        read_manifest(m,tmp_path)


def test_acceptance_metrics_with_unknown_and_comparison(tmp_path):
    from scripts.evaluate_iq_recordings import evaluate_multiple_models
    make_wav(tmp_path/"a.wav")
    make_wav(tmp_path/"b.wav")
    m=manifest(tmp_path)
    data=json.loads(m.read_text())
    data["recordings"].append({
        "path":"b.wav","mode":"UNKNOWN","session_id":"session-unknown",
        "device":"fake SDR","frequency_hz":145650000})
    m.write_text(json.dumps(data))
    class AlwaysAM:
        def predict(self,iq):
            return Classification("AM",.99,{k:(1 if k=="AM" else 0) for k in CLASSES})
    reports=evaluate_multiple_models(m,tmp_path,{"v2":AlwaysAM(),"v3":AlwaysAM()})
    assert set(reports["models"])=={"v2","v3"}
    x=reports["models"]["v2"]
    assert x["known_windows"]==4 and x["unknown_windows"]==4
    assert x["accuracy_top1"]==.5
    for t in ("0.8","0.95","0.99"):
        assert x["acceptance_curve"][t]["correct_known_accepted_rate"]==1
        assert x["acceptance_curve"][t]["unknown_false_accept_rate"]==1
    assert "session-unknown" not in json.dumps(reports)


def test_acceptance_metrics_when_all_known_or_unknown(tmp_path):
    make_wav(tmp_path/"a.wav")
    class Stub:
        def predict(self,iq):
            return Classification("AM",.99,{k:(1 if k=="AM" else 0) for k in CLASSES})
    known=evaluate(manifest(tmp_path),tmp_path,Stub())
    assert known["acceptance_curve"]["0.8"]["unknown_false_accept_rate"] is None
    unknown=evaluate(manifest(tmp_path,label="UNKNOWN"),tmp_path,Stub())
    assert unknown["acceptance_curve"]["0.8"]["known_coverage"] is None
    assert unknown["acceptance_curve"]["0.8"]["unknown_false_accept_rate"]==1
