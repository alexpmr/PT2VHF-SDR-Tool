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
    assert len(list(read_windows(dst, limit=2)))==2


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



@pytest.mark.parametrize("rate", [1_024_000, 2_048_000, 2_400_000])
def test_realistic_sdr_sample_rates_are_channelized(tmp_path, rate):
    from math import gcd
    src = tmp_path / "raw.wav"
    dst = tmp_path / "iq48.wav"
    # Simulated RF signal; no actual SDR input or performance claim.
    count = rate // 4
    make_iq(src, rate=rate, n=count, tone=13_400)
    result = convert(src, dst, 145_000_000, 145_013_400, chunk=35007)
    sr, data = read_complex(dst)
    assert sr == 48_000
    assert len(data) == 12_000
    assert result["resample_up"] == 48_000 // gcd(rate, 48_000)
    assert result["resample_down"] == rate // gcd(rate, 48_000)
    steady = data[800:-800]
    assert abs(np.mean(steady)) > .2
    assert np.std(steady) / abs(np.mean(steady)) < .02


@pytest.mark.parametrize("rate", [240_000, 1_024_000, 2_048_000])
@pytest.mark.parametrize("chunk", [257, 10_003, 65_536])
def test_polyphase_resampling_independent_of_disk_chunk_boundaries(
    tmp_path, rate, chunk
):
    src = tmp_path / "raw.wav"
    # Even at 2.048 MS/s, this produces >2048 output IQ samples.
    input_frames = 110_007
    make_iq(src, rate=rate, n=input_frames, tone=12_500)
    reference, candidate = tmp_path / "ref.wav", tmp_path / "out.wav"
    convert(src, reference, 145_500_000, 145_512_200, chunk=65_536)
    convert(src, candidate, 145_500_000, 145_512_200, chunk=chunk)
    _, first = read_complex(reference)
    _, second = read_complex(candidate)
    assert len(first) == len(second) == (
        (input_frames * 48_000 + rate - 1) // rate
    )
    np.testing.assert_allclose(first, second, atol=3 / 32768)


@pytest.mark.parametrize("rate", [1_024_000, 2_048_000])
def test_rational_channel_filter_rejects_outside_48k_band(tmp_path, rate):
    src, dest = tmp_path / "raw.wav", tmp_path / "centered.wav"
    make_iq(src, rate=rate, n=rate // 4, tone=4_000, blocker=62_000)
    convert(src, dest, 146_000_000, 146_004_000)
    _, iq = read_complex(dest)
    steady = iq[600:-600]
    assert abs(np.mean(steady)) > .20
    assert np.std(steady) / abs(np.mean(steady)) < .03


def test_source_below_48k_still_rejected(tmp_path):
    src, dest = tmp_path / "raw.wav", tmp_path / "iq.wav"
    make_iq(src, rate=32_000, n=16_000)
    with pytest.raises(ValueError, match="48 kS/s"):
        convert(src, dest, 146_000_000, 146_004_000)
    assert not dest.exists()



@pytest.mark.parametrize("rate", [48_000, 192_000, 1_024_000, 2_457_600])
@pytest.mark.parametrize("chunk", [1_003, 27_001])
def test_streaming_converter_matches_independent_full_file_polyphase_oracle(
    tmp_path, rate, chunk
):
    """Full-file SciPy oracle, independent from the converter's halo logic.

    The PCM16 source is decoded first; all output samples, including start,
    final partial block, NCO residual and boundary phase, are compared.
    """
    from math import gcd
    from scipy.signal import firwin, resample_poly

    src, dst = tmp_path / "radio_iq.wav", tmp_path / "channel.wav"
    n = 132_013
    rng = np.random.default_rng(25)
    t = np.arange(n, dtype=np.float64) / rate
    samples = (
        0.24 * np.exp(2j * np.pi * 8_400 * t)
        + 0.10 * np.exp(2j * np.pi * 9_750 * t)
        + 0.015 * (rng.normal(size=n) + 1j * rng.normal(size=n))
    )
    iq_pcm = np.empty((n, 2), dtype="<i2")
    iq_pcm[:, 0] = np.round(samples.real * 32767).astype("<i2")
    iq_pcm[:, 1] = np.round(samples.imag * 32767).astype("<i2")
    with wave.open(str(src), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(iq_pcm.tobytes())

    center, target = 145_000_000, 145_008_000
    result = convert(src, dst, center, target, chunk=chunk)
    _, actual = read_complex(dst)
    g = gcd(rate, 48_000)
    up, down = 48_000 // g, rate // g
    taps = firwin(20 * max(up, down) + 1, 0.90 / max(up, down),
                  window=("kaiser", 8.6))
    decoded = ((iq_pcm[:, 0].astype(np.float64)
                + 1j * iq_pcm[:, 1].astype(np.float64)) / 32768)
    mixed = decoded * np.exp(-2j * np.pi * 8_000 * np.arange(n) / rate)
    expected = resample_poly(mixed, up, down, window=taps)

    assert result["frames"] == len(expected) == len(actual)
    # Both WAV channels are rounded to PCM16: error bound one output LSB.
    assert np.max(np.abs(actual - expected)) < 2.5 / 32768


@pytest.mark.parametrize("rate", [1_000_001, 2_000_003])
def test_rate_with_extreme_rational_factor_fails_before_fir_allocation(
    tmp_path, rate, monkeypatch
):
    import scripts.prepare_iq_rf_capture as prepare

    src, dst = tmp_path / "input.wav", tmp_path / "out.wav"
    make_iq(src, rate=rate, n=rate//4)
    called = False

    def forbidden_fir(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("Unsafe FIR allocation")

    monkeypatch.setattr(prepare, "firwin", forbidden_fir)
    with pytest.raises(ValueError, match="high-complexity IQ resampling ratio"):
        convert(src, dst, 145_500_000, 145_504_000)
    assert not called
    assert not dst.exists()
