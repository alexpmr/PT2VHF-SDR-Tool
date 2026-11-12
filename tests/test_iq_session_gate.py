"""Research-only IQ gate regression tests with fake WAV and fake model."""
import json
import shutil
import wave

import numpy as np
import pytest

from scripts.iq_session_gate import audit, digest, rates, select, run


def wav(path, freq):
    t = np.arange(4096)/48000
    v = (np.sin(2*np.pi*freq*t)*15000).astype("<i2")
    iq = np.stack((v, v//2), axis=1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(48000)
        f.writeframes(iq.tobytes())


def manifest(root, name, prefix, offset):
    rows = []
    for i, label in enumerate(("AM", "UNKNOWN")):
        filename = f"{prefix}-{i}.wav"
        wav(root/filename, offset+i*270)
        rows.append({"path":filename, "mode":label,
                     "session_id":f"{prefix}-{i}", "device":"synthetic device",
                     "frequency_hz":145500000})
    file = root/name
    file.write_text(json.dumps({"recordings":rows}))
    return file


def test_audit_disjoint(tmp_path):
    a = manifest(tmp_path,"cal.json","cal",1200)
    b = manifest(tmp_path,"hold.json","hold",1700)
    cal, hold = audit(a,b,tmp_path)
    assert len(cal)==2 and len(hold)==2



@pytest.mark.parametrize("mixed_split", ["calibration", "holdout"])
def test_audit_rejects_known_unknown_from_same_session_with_other_sessions(
        tmp_path, mixed_split):
    """Synthetic regression: two session IDs can hide a mixed-label session.

    Previously this passed the aggregate session-count gate even though
    known/UNKNOWN rates shared a session and were not independent.
    """
    a = manifest(tmp_path, "cal.json", "cal", 1200)
    b = manifest(tmp_path, "hold.json", "hold", 1700)
    target = a if mixed_split == "calibration" else b
    doc = json.loads(target.read_text())
    # Make known and UNKNOWN observations share a session, while adding a
    # second distinct known session so the old len(sessions)>=2 check passes.
    doc["recordings"][1]["session_id"] = doc["recordings"][0]["session_id"]
    prefix = "cal" if mixed_split == "calibration" else "hold"
    extra_name = prefix + "-extra.wav"
    wav(tmp_path / extra_name, 3171 if mixed_split == "calibration" else 3283)
    doc["recordings"].append({
        "path": extra_name, "mode": "AM",
        "session_id": prefix + "-extra",
        "device": "synthetic device", "frequency_hz": 145500000,
    })
    target.write_text(json.dumps(doc))
    assert len({row["session_id"] for row in doc["recordings"]}) == 2
    with pytest.raises(ValueError, match=mixed_split + " session mixes known and UNKNOWN"):
        audit(a, b, tmp_path)


def test_audit_rejects_overlapping_sessions(tmp_path):
    a = manifest(tmp_path,"cal.json","cal",1200)
    b = manifest(tmp_path,"hold.json","hold",1700)
    doc = json.loads(b.read_text())
    doc["recordings"][0]["session_id"]="cal-0"
    b.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match="Overlapping calibration"):
        audit(a,b,tmp_path)


def test_audit_rejects_copied_wave_even_when_renamed(tmp_path):
    a = manifest(tmp_path,"cal.json","cal",1200)
    b = manifest(tmp_path,"hold.json","hold",1700)
    shutil.copyfile(tmp_path/"cal-0.wav",tmp_path/"hold-0.wav")
    assert digest(tmp_path/"cal-0.wav")==digest(tmp_path/"hold-0.wav")
    with pytest.raises(ValueError,match="Identical WAV content"):
        audit(a,b,tmp_path)


def test_select_threshold_from_calibration_only():
    rows=[("AM","AM",.97,"known"),("AM","AM",.86,"known"),
          ("UNKNOWN","AM",.94,"unknown"),("UNKNOWN","UNKNOWN",.99,"unknown")]
    chosen,curve=select(rows,.1,.5)
    assert len(curve)==5
    assert chosen["threshold"]==pytest.approx(.95)
    assert chosen["known_correct_coverage"]==.5


def test_no_threshold_when_high_confidence_unknown():
    rows=[("AM","AM",.99,"known"),("UNKNOWN","AM",1.0,"unknown")]
    chosen,_=select(rows)
    assert chosen is None


def test_no_threshold_when_coverage_is_zero():
    rows=[("AM","AM",.20,"known"),("UNKNOWN","AM",.90,"unknown")]
    chosen,_=select(rows)
    assert chosen is None


def test_session_macro_prevents_long_quiet_capture_masking_noisy_session():
    rows=[("AM","AM",.99,"known")]
    rows += [("UNKNOWN","UNKNOWN",.99,"quiet") for _ in range(100)]
    rows += [("UNKNOWN","AM",.99,"bad")]
    observed=rates(rows,.95)
    assert observed["unknown_false_accept_rate"] < .1
    assert observed["unknown_session_macro_false_accept"] == .5
    chosen,_=select(rows,.1,.5)
    assert chosen is None


def test_fail_closed_end_to_end(tmp_path):
    from pt2vhf.dsp.iq_classifier import Classification, CLASSES
    a=manifest(tmp_path,"cal.json","cal",1200)
    b=manifest(tmp_path,"hold.json","hold",1700)
    class AlwaysAM:
        def predict(self, iq):
            return Classification("AM", .99,
                {k:(1.0 if k=="AM" else 0.0) for k in CLASSES})
    output=run(a,b,tmp_path,AlwaysAM())
    assert output["decision"]=="NO_ACCEPTABLE_THRESHOLD"
    assert output["selected_threshold"] is None
    assert output["holdout_result"] is None
    assert output["operationally_validated"] is False


@pytest.mark.parametrize("bad",[float("nan"),-1,2])
def test_bad_limits_rejected(bad):
    rows=[("AM","AM",.96,"known"),("UNKNOWN","UNKNOWN",.96,"unknown")]
    with pytest.raises(ValueError,match="Invalid limits"):
        select(rows,max_far=bad)



def test_audit_rejects_partial_iq_window_reuse_in_modified_wav(tmp_path):
    """Different complete files are still a leak if a real IQ window was copied."""
    a = manifest(tmp_path, "cal.json", "cal", 1200)
    b = manifest(tmp_path, "hold.json", "hold", 1700)
    with wave.open(str(tmp_path / "cal-0.wav"), "rb") as wav_file:
        copied_first_window = wav_file.readframes(2048)
    with wave.open(str(tmp_path / "hold-0.wav"), "rb") as wav_file:
        original = wav_file.readframes(4096)
    with wave.open(str(tmp_path / "hold-0.wav"), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48000)
        wav_file.writeframes(copied_first_window + original[2048*4:])
    assert digest(tmp_path / "cal-0.wav") != digest(tmp_path / "hold-0.wav")
    with pytest.raises(ValueError, match="Identical IQ window"):
        audit(a, b, tmp_path)



def test_audit_rejects_interior_window_reuse_with_distinct_edges(tmp_path):
    """Synthetic long WAVs: copied middle IQ must not evade bounded split audit."""
    a = manifest(tmp_path, "cal.json", "cal", 1200)
    b = manifest(tmp_path, "hold.json", "hold", 1700)

    def long_wav(path, base_frequency):
        t = np.arange(2048) / 48000
        with wave.open(str(path), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(48000)
            for index in range(80):
                tone = (12000 * np.sin(2 * np.pi *
                                     (base_frequency + 11 * index) * t)).astype("<i2")
                out.writeframes(np.stack((tone, tone // 2), axis=1).tobytes())

    cal_wav = tmp_path / "cal-0.wav"
    hold_wav = tmp_path / "hold-0.wav"
    long_wav(cal_wav, 900)
    long_wav(hold_wav, 2700)
    # Distinct file hashes and edge windows; only window 40 is shared.
    with wave.open(str(cal_wav), "rb") as source:
        source.setpos(40 * 2048)
        reused = source.readframes(2048)
    with wave.open(str(hold_wav), "rb") as source:
        original = source.readframes(80 * 2048)
    start = 40 * 2048 * 4  # stereo PCM16 = 4 bytes per IQ sample
    with wave.open(str(hold_wav), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(original[:start] + reused + original[start + len(reused):])

    assert digest(cal_wav) != digest(hold_wav)
    with pytest.raises(ValueError, match="Identical IQ window"):
        audit(a, b, tmp_path)

def test_sampled_window_hashes_reproducible_and_bounded(tmp_path):
    from scripts.iq_session_gate import sampled_iq_window_hashes
    manifest(tmp_path, "cal.json", "cal", 1400)
    path = tmp_path / "cal-0.wav"
    a = sampled_iq_window_hashes(path)
    b = sampled_iq_window_hashes(path, edge_windows=1)
    assert a and b
    assert b.issubset(a)
    with pytest.raises(ValueError, match="positive"):
        sampled_iq_window_hashes(path, edge_windows=0)


def test_holdout_gate_requires_three_sessions_and_two_devices(tmp_path, monkeypatch):
    """Synthetic labels: strong window scores cannot replace SDR/session diversity."""
    import scripts.iq_session_gate as gate
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)

    def perfect_observations(rows, model, max_windows, *, accounting=None):
        if accounting is not None:
            accounting.update({"minimum_session_pipeline_coverage": 1.0,
                               "pipeline_coverage": 1.0})
        return [(label, label, .99, session) for _, label, session, _ in rows]

    monkeypatch.setattr(gate, "observations", perfect_observations)
    two_sessions = gate.run(cal, hold, tmp_path, object())
    assert two_sessions["decision"] == "HOLDOUT_INSUFFICIENT_DIVERSITY"
    assert two_sessions["holdout_diversity_gate_passed"] is False
    assert two_sessions["holdout_result"]["unknown_false_accept_rate"] == 0
    assert two_sessions["operationally_validated"] is False

    wav(tmp_path / "hold-2.wav", 2500)
    doc = json.loads(hold.read_text())
    doc["recordings"].append({
        "path": "hold-2.wav", "mode": "AM", "session_id": "hold-2",
        "device": "synthetic device", "frequency_hz": 145500000,
    })
    hold.write_text(json.dumps(doc))
    one_device = gate.run(cal, hold, tmp_path, object())
    assert one_device["holdout_sessions"] == 3
    assert one_device["decision"] == "HOLDOUT_INSUFFICIENT_DIVERSITY"

    doc["recordings"][-1]["device"] = "independent synthetic SDR"
    hold.write_text(json.dumps(doc))
    # Three total sessions and two devices still leave UNKNOWN represented
    # by a single session on a single SDR: never accept this as OOD QA.
    insufficient_ood = gate.run(cal, hold, tmp_path, object())
    assert insufficient_ood["decision"] == "HOLDOUT_INSUFFICIENT_DIVERSITY"
    assert insufficient_ood["holdout_unknown_sessions"] == 1
    assert insufficient_ood["holdout_unknown_devices"] == 1

    wav(tmp_path / "hold-3.wav", 3100)
    doc["recordings"].append({
        "path": "hold-3.wav", "mode": "UNKNOWN", "session_id": "hold-3",
        "device": "synthetic device", "frequency_hz": 145500000,
    })
    hold.write_text(json.dumps(doc))
    one_unknown_device = gate.run(cal, hold, tmp_path, object())
    assert one_unknown_device["holdout_unknown_sessions"] == 2
    assert one_unknown_device["decision"] == "HOLDOUT_INSUFFICIENT_DIVERSITY"
    doc["recordings"][-1]["device"] = "independent synthetic SDR"
    hold.write_text(json.dumps(doc))
    diverse = gate.run(cal, hold, tmp_path, object())
    assert diverse["decision"] == "HOLDOUT_EVALUATED"
    assert diverse["holdout_diversity_gate_passed"] is True
    assert diverse["distinct_holdout_devices"] == 2
    assert diverse["holdout_known_sessions"] == diverse["holdout_unknown_sessions"] == 2
    assert diverse["holdout_known_devices"] == diverse["holdout_unknown_devices"] == 2
    assert diverse["operationally_validated"] is False


def test_observations_account_for_silent_and_dc_rejections(tmp_path):
    """Synthetic-only coverage: preprocessing exclusions are not neural UNKNOWN."""
    from pt2vhf.dsp.iq_classifier import Classification, CLASSES, IQClassifier
    from scripts.iq_session_gate import observations
    path = tmp_path / "mixed.wav"
    t = np.arange(2048) / 48000
    tone = (np.sin(2 * np.pi * 1250 * t) * 15000).astype("<i2")
    frames = np.zeros((4 * 2048, 2), dtype="<i2")
    frames[:2048, 0] = tone
    frames[:2048, 1] = tone // 2
    frames[2048:4096, 0] = 1500  # DC-only; nonzero, but not inferable
    # Last two windows are silent and must not count as UNKNOWN.
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(frames.tobytes())

    class Guarded:
        def predict(self, iq):
            IQClassifier.features(iq)
            return Classification("AM", .99,
                                  {k: (1.0 if k == "AM" else 0.0) for k in CLASSES})

    accounting = {}
    rows = [(path, "AM", "private-session", "synthetic SDR")]
    observed = observations(rows, Guarded(), 100, accounting=accounting)
    assert len(observed) == 1
    assert accounting["windows_selected"] == 4
    assert accounting["windows_inferred"] == 1
    assert accounting["windows_rejected_preprocessing"] == 1
    assert accounting["windows_skipped_silence"] == 2
    assert accounting["pipeline_coverage"] == .25
    assert accounting["minimum_session_pipeline_coverage"] == .25
    assert "private-session" not in json.dumps(accounting)


def test_holdout_rejects_low_pipeline_coverage_even_with_perfect_predictions(
        tmp_path, monkeypatch):
    """Synthetic stub: perfect conditional scores cannot hide excluded windows."""
    import scripts.iq_session_gate as gate
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)
    wav(tmp_path / "hold-2.wav", 2500)
    doc = json.loads(hold.read_text())
    doc["recordings"].append({
        "path": "hold-2.wav", "mode": "AM", "session_id": "hold-2",
        "device": "independent synthetic SDR", "frequency_hz": 145500000,
    })
    wav(tmp_path / "hold-3.wav", 2900)
    doc["recordings"].append({
        "path": "hold-3.wav", "mode": "UNKNOWN", "session_id": "hold-3",
        "device": "independent synthetic SDR", "frequency_hz": 145500000,
    })
    hold.write_text(json.dumps(doc))

    calls = 0

    def perfect_but_low_coverage(rows, model, max_windows, *, accounting=None):
        nonlocal calls
        calls += 1
        if accounting is not None:
            coverage = 1.0 if calls == 1 else .25
            accounting.update({"minimum_session_pipeline_coverage": coverage,
                               "pipeline_coverage": coverage})
        return [(label, label, .99, session) for _, label, session, _ in rows]

    monkeypatch.setattr(gate, "observations", perfect_but_low_coverage)
    report = gate.run(cal, hold, tmp_path, object())
    assert report["holdout_diversity_gate_passed"] is True
    assert report["holdout_result"]["unknown_false_accept_rate"] == 0
    assert report["decision"] == "HOLDOUT_INSUFFICIENT_PIPELINE_COVERAGE"
    assert report["holdout_pipeline"]["minimum_session_pipeline_coverage"] == .25
    assert report["operationally_validated"] is False
    with pytest.raises(ValueError, match="minimum pipeline coverage"):
        gate.run(cal, hold, tmp_path, object(), min_pipeline_coverage=float("nan"))


@pytest.mark.parametrize("copied_index", [20, 60])
def test_audit_rejects_quarter_position_iq_reuse(tmp_path, copied_index):
    """Synthetic 80-window WAVs: reused quarter excerpts must fail split QA."""
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)
    first = np.random.default_rng(904).integers(
        -8000, 8000, size=(80 * 2048, 2), dtype=np.int16)
    second = np.random.default_rng(905).integers(
        -8000, 8000, size=(80 * 2048, 2), dtype=np.int16)
    start = copied_index * 2048
    second[start:start + 2048] = first[start:start + 2048]

    for filename, pcm in (("cal-0.wav", first), ("hold-0.wav", second)):
        with wave.open(str(tmp_path / filename), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(48000)
            out.writeframes(pcm.tobytes())

    assert digest(tmp_path / "cal-0.wav") != digest(tmp_path / "hold-0.wav")
    with pytest.raises(ValueError, match="Identical IQ window"):
        audit(cal, hold, tmp_path)


@pytest.mark.parametrize("mass", [0.0, 0.5, 1.2])
def test_observations_reject_unnormalized_model_probabilities(tmp_path, mass):
    """Synthetic-only: UNKNOWN thresholds require a valid probability simplex."""
    from pt2vhf.dsp.iq_classifier import Classification, CLASSES
    from scripts.iq_session_gate import observations

    source = tmp_path / "synthetic.wav"
    wav(source, 1200)

    class Malformed:
        def predict(self, iq):
            probabilities = {name: 0.0 for name in CLASSES}
            probabilities["AM"] = mass
            return Classification("AM", mass, probabilities)

    with pytest.raises(ValueError, match="not normalized|Invalid model probability"):
        observations([(source, "AM", "private-session", "synthetic SDR")],
                     Malformed(), max_windows=2)


def test_observations_accept_softmax_probability_roundoff(tmp_path):
    """Small floating-point sum error must not reject valid softmax output."""
    from pt2vhf.dsp.iq_classifier import Classification, CLASSES
    from scripts.iq_session_gate import observations

    source = tmp_path / "synthetic.wav"
    wav(source, 1400)

    class Rounded:
        def predict(self, iq):
            probabilities = {name: 0.0 for name in CLASSES}
            probabilities["AM"] = 0.999999
            return Classification("AM", 0.999999, probabilities)

    observed = observations([(source, "AM", "private-session", "synthetic SDR")],
                            Rounded(), max_windows=2)
    assert len(observed) == 2
    assert all(item[1] == "AM" for item in observed)
