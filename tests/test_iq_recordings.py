"""Offline IQ WAV evaluation tests; test fixtures are synthetic, NOT RF."""
import json
import wave
import numpy as np
import pytest
from pt2vhf.dsp.iq_classifier import CLASSES, Classification, IQClassifier
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


def test_long_wav_samples_beginning_middle_and_end_without_overlap(tmp_path):
    """Synthetic segments expose the previous first-N-window selection bias."""
    wav = tmp_path / "long.wav"
    with wave.open(str(wav), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        for i in range(12):
            frames = np.zeros((2048, 2), dtype="<i2")
            frames[:, 0] = 1000 * (i + 1)
            out.writeframes(frames.tobytes())
    selected = list(read_windows(wav, limit=3))
    assert len(selected) == 3
    assert [round(float(np.real(iq).mean() * 32768)) for iq in selected] == [
        1000, 6000, 12000
    ]
    assert len(list(read_windows(wav, limit=20))) == 12
    # With only one selected window, a startup-only sample would return 1000.
    center_only = list(read_windows(wav, limit=1, with_index=True))
    assert len(center_only) == 1
    assert center_only[0][0] == 5
    assert round(float(center_only[0][1].real.mean() * 32768)) == 6000


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


def test_session_bootstrap_interval_is_deterministic_and_withheld_when_sparse():
    from scripts.evaluate_iq_recordings import session_bootstrap_accuracy
    assert session_bootstrap_accuracy([[8, 8], [8, 0]]) is None
    counts = [[20, 20], [20, 10], [20, 0], [20, 15]]
    one = session_bootstrap_accuracy(counts, resamples=500, seed=77)
    two = session_bootstrap_accuracy(counts, resamples=500, seed=77)
    assert one == two
    assert one["independent_sessions"] == 4
    assert 0 <= one["lower"] <= .5625 <= one["upper"] <= 1
    with pytest.raises(ValueError, match="resamples"):
        session_bootstrap_accuracy(counts, resamples=0)


def test_offline_report_session_ci_is_private_and_session_based(tmp_path):
    for n in ("a.wav", "b.wav", "c.wav"):
        make_wav(tmp_path / n)
    m = manifest(tmp_path)
    doc = json.loads(m.read_text())
    doc["recordings"].extend([
        {"path": "b.wav", "mode": "UNKNOWN", "session_id": "sensitive-B",
         "device": "fake SDR", "frequency_hz": 145650000},
        {"path": "c.wav", "mode": "AM", "session_id": "sensitive-C",
         "device": "fake SDR", "frequency_hz": 145650000},
    ])
    m.write_text(json.dumps(doc))
    class AlwaysAM:
        def predict(self, iq):
            return Classification("AM", .99,
                                  {k: (1 if k == "AM" else 0) for k in CLASSES})
    report = evaluate(m, tmp_path, AlwaysAM())
    assert report["session_macro_accuracy"] == pytest.approx(2 / 3)
    ci = report["session_macro_accuracy_ci95"]
    assert ci["independent_sessions"] == 3
    assert 0 <= ci["lower"] <= (2 / 3) <= ci["upper"] <= 1
    assert report["session_accuracy_summary"]["min"] == 0
    assert report["session_accuracy_summary"]["max"] == 1
    assert report["session_accuracy_summary"]["session_ids_excluded"] is True
    assert "sensitive-B" not in json.dumps(report)
    assert "sensitive-C" not in json.dumps(report)


@pytest.mark.parametrize("confidence,accepted_at_08", [(0.7, 0.0), (0.9, 1.0)])
def test_unknown_confidence_gate_is_respected_without_biasing_threshold_curve(
        tmp_path, confidence, accepted_at_08):
    """Synthetic stub: effective UNKNOWN and raw top-1 are different decisions."""
    for name in ("a.wav", "b.wav"):
        make_wav(tmp_path / name)
    m = manifest(tmp_path)
    doc = json.loads(m.read_text())
    doc["recordings"].append({
        "path": "b.wav", "mode": "UNKNOWN", "session_id": "independent-unknown",
        "device": "fake SDR", "frequency_hz": 145650000,
    })
    m.write_text(json.dumps(doc))

    class Gated:
        def predict(self, iq):
            probs = {name: 0.0 for name in CLASSES}
            probs["AM"] = confidence
            probs["UNKNOWN"] = 1.0 - confidence
            # Simulate min_confidence > confidence, as in IQClassifier.predict.
            return Classification("UNKNOWN", confidence, probs)

    report = evaluate(m, tmp_path, Gated())
    # The classifier returns UNKNOWN for both classes, not raw top-1 AM.
    assert report["accuracy_top1"] == 0.5
    assert report["per_class_recall"]["UNKNOWN"] == 1.0
    assert report["per_class_recall"]["AM"] == 0.0
    assert report["session_macro_accuracy"] == 0.5
    # Threshold sweeps evaluate the raw top class at each independent gate.
    assert report["acceptance_curve"]["0.8"]["unknown_false_accept_rate"] == accepted_at_08
    assert report["acceptance_curve"]["0.8"]["known_coverage"] == accepted_at_08
    assert report["acceptance_curve"]["0.95"]["unknown_false_accept_rate"] == 0.0
    assert report["acceptance_curve"]["0.95"]["known_coverage"] == 0.0


def make_flat_wav(path, amplitude):
    """Synthetic IQ: zero RMS or nonzero DC, never a real RF recording."""
    frames = np.zeros((8192, 2), dtype="<i2")
    frames[:, 0] = amplitude
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(frames.tobytes())


def test_silent_and_dc_windows_are_accounted_without_neural_credit(tmp_path):
    make_flat_wav(tmp_path / "silent.wav", 0)
    make_flat_wav(tmp_path / "dc.wav", 1200)
    m = manifest(tmp_path, filename="silent.wav", label="UNKNOWN")
    doc = json.loads(m.read_text())
    doc["recordings"].append({
        "path": "dc.wav", "mode": "UNKNOWN", "session_id": "private-dc",
        "device": "fake SDR", "frequency_hz": 145650000,
    })
    m.write_text(json.dumps(doc))

    class Guarded:
        def predict(self, iq):
            IQClassifier.features(iq)
            pytest.fail("DC-only input must not reach a neural prediction")

    report = evaluate(m, tmp_path, Guarded())
    assert report["windows_selected"] == 8
    assert report["windows_skipped_silence"] == 4
    assert report["windows_rejected_preprocessing"] == 4
    assert report["windows_rejected_preprocessing_unknown"] == 4
    assert report["windows_inferred"] == report["sample_windows"] == 0
    assert report["pipeline_coverage"] == 0
    assert report["accuracy_top1"] is None
    assert report["session_macro_accuracy"] is None
    assert report["session_accuracy_summary"]["sessions_without_inference"] == 2
    assert report["acceptance_curve"]["0.8"]["unknown_false_accept_rate"] is None
    assert report["per_class_recall"]["UNKNOWN"] is None
    assert "private-dc" not in json.dumps(report)


def test_mixed_signal_and_dc_coverage_does_not_inflate_unknown_recall(tmp_path):
    make_wav(tmp_path / "a.wav")
    make_flat_wav(tmp_path / "dc.wav", 1500)
    m = manifest(tmp_path)
    doc = json.loads(m.read_text())
    doc["recordings"].append({
        "path": "dc.wav", "mode": "UNKNOWN", "session_id": "private-unknown",
        "device": "fake SDR", "frequency_hz": 145650000,
    })
    m.write_text(json.dumps(doc))

    class Guarded:
        def predict(self, iq):
            IQClassifier.features(iq)
            return Classification("AM", .99,
                                  {k: (1 if k == "AM" else 0) for k in CLASSES})

    report = evaluate(m, tmp_path, Guarded())
    assert report["windows_selected"] == 8
    assert report["windows_inferred"] == 4
    assert report["windows_rejected_preprocessing"] == 4
    assert report["pipeline_coverage"] == .5
    assert report["accuracy_top1"] == 1
    assert report["per_class_recall"]["UNKNOWN"] is None
    assert report["session_pipeline_coverage_summary"]["min"] == 0
    assert report["session_pipeline_coverage_summary"]["max"] == 1
    assert report["session_accuracy_summary"]["sessions_without_inference"] == 1


def test_unexpected_prediction_error_is_not_silently_swallowed(tmp_path):
    make_wav(tmp_path / "a.wav")
    class Broken:
        def predict(self, iq):
            raise ValueError("invalid model output")
    with pytest.raises(ValueError, match="invalid model output"):
        evaluate(manifest(tmp_path), tmp_path, Broken())


def test_read_windows_exposes_silence_selection_counts(tmp_path):
    make_flat_wav(tmp_path / "silent.wav", 0)
    stats = {}
    assert list(read_windows(tmp_path / "silent.wav", limit=3, stats=stats)) == []
    assert stats == {"selected": 3, "skipped_silence": 3}


def test_read_windows_optional_indices_preserve_default(tmp_path):
    wav = tmp_path / "indexed.wav"
    make_wav(wav)
    plain = list(read_windows(wav, limit=3))
    indexed = list(read_windows(wav, limit=3, with_index=True))
    assert [i for i, _ in indexed] == [0, 1, 3]
    for x, (_, y) in zip(plain, indexed):
        np.testing.assert_array_equal(x, y)


def test_multi_model_comparison_rejects_different_inferred_cohorts(tmp_path):
    """Synthetic exclusions with equal totals must not masquerade as a fair comparison."""
    from scripts.evaluate_iq_recordings import evaluate_multiple_models
    wav = tmp_path / "varying.wav"
    n = 2048
    tone = np.sin(2 * np.pi * 1100 * np.arange(n) / 48000)
    data = np.zeros((4 * n, 2), dtype="<i2")
    for index, amplitude in enumerate((2000, 12000, 2000, 12000)):
        samples = np.round(amplitude * tone).astype("<i2")
        data[index * n:(index + 1) * n, 0] = samples
        data[index * n:(index + 1) * n, 1] = samples // 2
    with wave.open(str(wav), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(data.tobytes())

    class RejectByLevel:
        def __init__(self, low):
            self.low = low

        def predict(self, iq):
            is_low = float(np.sqrt(np.mean(np.abs(iq)**2))) < 0.15
            if is_low == self.low:
                raise ValueError("No usable RF signal (DC-only or unresolved carrier)")
            return Classification("AM", 0.99,
                                  {k: (1 if k == "AM" else 0) for k in CLASSES})

    m = manifest(tmp_path, filename="varying.wav")
    a, b = RejectByLevel(True), RejectByLevel(False)
    left, right = evaluate(m, tmp_path, a), evaluate(m, tmp_path, b)
    assert left["windows_inferred"] == right["windows_inferred"] == 2
    assert left["windows_rejected_preprocessing"] == right["windows_rejected_preprocessing"] == 2
    with pytest.raises(ValueError, match="did not infer the same IQ windows"):
        evaluate_multiple_models(m, tmp_path, {"v2": a, "v3": b})


@pytest.mark.parametrize("corruption", [
    "missing_class", "nan", "infinite", "negative", "unnormalized", "string", "boolean", "complex",
])
def test_offline_evaluation_rejects_invalid_softmax_before_rf_metrics(tmp_path, corruption):
    """Synthetic stubs: malformed output must not make UNKNOWN FAR look safe."""
    make_wav(tmp_path / "a.wav")

    class Broken:
        def predict(self, iq):
            probabilities = {name: (1.0 if name == "AM" else 0.0)
                             for name in CLASSES}
            if corruption == "missing_class":
                probabilities.pop("CW")
            elif corruption == "nan":
                probabilities["AM"] = float("nan")
            elif corruption == "infinite":
                probabilities["AM"] = float("inf")
            elif corruption == "negative":
                probabilities["UNKNOWN"] = -0.1
            elif corruption == "unnormalized":
                probabilities["AM"] = 0.7
            elif corruption == "string":
                probabilities["AM"] = "1.0"
            elif corruption == "boolean":
                probabilities["AM"] = True
            elif corruption == "complex":
                probabilities["AM"] = np.complex64(1 + 0.5j)
            return Classification("AM", 0.99, probabilities)

    with pytest.raises(ValueError, match="Invalid model probabilit"):
        evaluate(manifest(tmp_path), tmp_path, Broken())


@pytest.mark.parametrize("bad_confidence", [float("nan"), float("inf"), -0.1, 1.1, "0.99", True, np.complex64(0.99 + 0.1j)])
def test_offline_evaluation_rejects_invalid_confidence(tmp_path, bad_confidence):
    make_wav(tmp_path / "a.wav")

    class Broken:
        def predict(self, iq):
            return Classification("AM", bad_confidence,
                                  {name: (1.0 if name == "AM" else 0.0)
                                   for name in CLASSES})

    with pytest.raises(ValueError, match="Invalid model confidence"):
        evaluate(manifest(tmp_path), tmp_path, Broken())


def test_offline_threshold_sweep_uses_softmax_not_stale_confidence(tmp_path):
    """A stale low confidence must not falsely suppress UNKNOWN acceptance."""
    make_wav(tmp_path / "a.wav")
    make_wav(tmp_path / "b.wav")
    m = manifest(tmp_path)
    document = json.loads(m.read_text())
    document["recordings"].append({
        "path": "b.wav", "mode": "UNKNOWN",
        "session_id": "independent-unknown", "device": "fake SDR",
        "frequency_hz": 145650000,
    })
    m.write_text(json.dumps(document))

    class StaleConfidence:
        def predict(self, iq):
            return Classification("AM", 0.01,
                                  {name: (1.0 if name == "AM" else 0.0)
                                   for name in CLASSES})

    report = evaluate(m, tmp_path, StaleConfidence())
    assert report["acceptance_curve"]["0.99"]["unknown_false_accept_rate"] == 1.0
    assert report["acceptance_curve"]["0.99"]["known_coverage"] == 1.0
    assert report["high_confidence_error_rate"] == 0.5
