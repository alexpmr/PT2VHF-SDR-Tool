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
