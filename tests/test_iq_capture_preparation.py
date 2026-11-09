"""Channelized 48k IQ WAV tests use synthetic tones, not real RF."""
import json
import wave
import numpy as np
import pytest

from scripts.prepare_iq_rf_capture import convert, append_manifest
from scripts.evaluate_iq_recordings import read_manifest, read_windows


def make_iq(path, rate=240000, n=120000, tone=12500, blocker=None):
    t=np.arange(n)/rate
    x=.4*np.exp(2j*np.pi*tone*t)
    if blocker is not None:
        x+=.35*np.exp(2j*np.pi*blocker*t)
    inter=np.empty(2*n,dtype="<i2")
    inter[0::2]=np.round(x.real*32767).astype("<i2")
    inter[1::2]=np.round(x.imag*32767).astype("<i2")
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(inter.tobytes())


def read_complex(path):
    with wave.open(str(path),"rb") as w:
        rate=w.getframerate()
        pairs=np.frombuffer(w.readframes(w.getnframes()),dtype="<i2").reshape(-1,2)
    return rate,(pairs[:,0].astype(np.float32)+1j*pairs[:,1].astype(np.float32))/32768


def test_channel_is_shifted_to_dc_and_output_decimated(tmp_path):
    src,dst=tmp_path/"original.wav",tmp_path/"channel.wav"
    make_iq(src)
    meta=convert(src,dst,145_500_000,145_512_500,chunk=12345)
    fs,iq=read_complex(dst)
    assert fs==48_000
    assert len(iq)==24_000==meta["frames"]
    # Ignore FIR opening and closing; should be constant-phase after conversion.
    steady=iq[500:-500]
    assert abs(np.mean(steady))>.20
    assert np.std(steady)/abs(np.mean(steady))<.02
    assert len(list(read_windows(dst, max_windows=2)))==2


@pytest.mark.parametrize("chunk",[257,5000,65536])
def test_fir_and_oscillator_phase_are_continuous_across_chunks(tmp_path,chunk):
    src=tmp_path/"source.wav"
    make_iq(src,n=24000,tone=15100)
    a,b=tmp_path/"a.wav",tmp_path/"b.wav"
    convert(src,a,100e6,100e6+14700,chunk=16384)
    convert(src,b,100e6,100e6+14700,chunk=chunk)
    _,x=read_complex(a)
    _,y=read_complex(b)
    assert len(x)==len(y)==4800
    np.testing.assert_allclose(x,y,atol=3/32768)


def test_out_of_band_blocker_is_attenuated(tmp_path):
    src=tmp_path/"source.wav"
    dst=tmp_path/"channel.wav"
    make_iq(src,tone=4000,blocker=53000)
    convert(src,dst,145_000_000,145_004_000)
    _,iq=read_complex(dst)
    steady=iq[500:-500]
    assert abs(np.mean(steady))>.20
    assert np.std(steady)/abs(np.mean(steady))<.025


def test_manifest_compatible_with_iq_evaluator(tmp_path):
    src=tmp_path/"input.wav"
    root=tmp_path/"prepared"
    root.mkdir()
    out=root/"nfm.wav"
    make_iq(src)
    convert(src,out,145_500_000,145_512_500)
    m=root/"manifest.json"
    append_manifest(m,root,out,"NFM","session-001","RTL-SDR V4",145_512_500)
    rows=read_manifest(m,root)
    assert len(rows)==1
    assert rows[0][1:] == ("NFM","session-001","RTL-SDR V4")
    assert json.loads(m.read_text())["recordings"][0]["path"]=="nfm.wav"
    with pytest.raises(ValueError,match="already"):
        append_manifest(m,root,out,"NFM","session-002","RTL-SDR V4",145_512_500)


def test_invalid_inputs_do_not_create_an_output(tmp_path):
    src=tmp_path/"raw.wav"
    dst=tmp_path/"out.wav"
    make_iq(src,n=5000)
    with pytest.raises(ValueError,match="too short"):
        convert(src,dst,145e6,145e6)
    make_iq(src)
    with pytest.raises(ValueError,match="Nyquist edge"):
        convert(src,dst,145e6,145e6+100000)
    with pytest.raises(ValueError,match="positive and finite"):
        convert(src,dst,float("nan"),145e6)
    assert not dst.exists()


def test_refuse_overwrite_or_manifest_escape(tmp_path):
    src=tmp_path/"raw.wav"
    dst=tmp_path/"out.wav"
    make_iq(src)
    dst.write_bytes(b"untouched")
    with pytest.raises(FileExistsError,match="overwrite"):
        convert(src,dst,145e6,145e6)
    assert dst.read_bytes()==b"untouched"
    with pytest.raises(ValueError,match="outside"):
        append_manifest(tmp_path/"m.json",tmp_path/"different",dst,"AM","s","d",145e6)
    with pytest.raises(ValueError,match="unsupported"):
        append_manifest(tmp_path/"m.json",tmp_path,dst,"WFM","s","d",145e6)
