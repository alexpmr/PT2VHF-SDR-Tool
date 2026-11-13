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
        return [(label, label, .99, session, device)
                for _, label, session, device in rows]

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
    assert diverse["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_COVERAGE"
    assert diverse["holdout_class_coverage_gate_passed"] is False
    assert diverse["missing_known_classes_holdout"] == ["CW", "LSB", "NFM", "USB"]
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
    assert observed[0][4] == "synthetic SDR"
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
        return [(label, label, .99, session, device)
                for _, label, session, device in rows]

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


def test_device_worst_case_blocks_ood_masked_by_many_good_sessions():
    """Synthetic: session-macro and pooled FAR can hide a failed SDR."""
    known = [("AM", "AM", .99, "known-a", "sdr-a"),
             ("AM", "AM", .99, "known-b", "sdr-b")]
    unknown = [("UNKNOWN", "UNKNOWN", .99, f"quiet-{i}", "sdr-a")
               for i in range(20)]
    unknown.append(("UNKNOWN", "AM", .99, "bad-unknown", "sdr-b"))
    rows = known + unknown
    measured = rates(rows, .95)
    assert measured["unknown_false_accept_rate"] == pytest.approx(1 / 21)
    assert measured["unknown_session_macro_false_accept"] == pytest.approx(1 / 21)
    assert measured["unknown_worst_device_false_accept_rate"] == 1.0
    assert measured["known_worst_device_correct_coverage"] == 1.0
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None
    assert "sdr-a" not in json.dumps(measured)
    assert "sdr-b" not in json.dumps(measured)


def test_device_worst_case_blocks_known_coverage_masked_by_many_sessions():
    """Synthetic: good aggregate known recall cannot mask a failed SDR."""
    known = [("AM", "AM", .99, f"good-{i}", "sdr-a")
             for i in range(20)]
    known.append(("AM", "UNKNOWN", .99, "bad-known", "sdr-b"))
    unknown = [("UNKNOWN", "UNKNOWN", .99, "unknown-a", "sdr-a"),
               ("UNKNOWN", "UNKNOWN", .99, "unknown-b", "sdr-b")]
    rows = known + unknown
    measured = rates(rows, .95)
    assert measured["known_session_macro_coverage"] == pytest.approx(20 / 21)
    assert measured["known_worst_device_correct_coverage"] == 0.0
    assert measured["unknown_worst_device_false_accept_rate"] == 0.0
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None


def test_iq_device_metadata_required_and_consistent_for_threshold_gate():
    """Legacy four-field rows remain usable only in standalone rate tests."""
    rows = [("AM", "AM", .99, "known", "sdr-a"),
            ("UNKNOWN", "UNKNOWN", .99, "unknown", "sdr-b")]
    with pytest.raises(ValueError, match="Inconsistent IQ observation device metadata"):
        rates([rows[0], rows[1][:4]], .95)
    legacy = rates([row[:4] for row in rows], .95)
    assert legacy["unknown_worst_device_false_accept_rate"] is None
    assert legacy["known_worst_device_correct_coverage"] is None


def test_end_to_end_holdout_fails_when_one_sdr_accepts_unknown(tmp_path, monkeypatch):
    """Synthetic holdout: global/session FAR 50% can pass a 60% budget,
    but a device with 100% false acceptance must still fail.
    """
    import scripts.iq_session_gate as gate
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)
    doc = json.loads(hold.read_text())
    for index, label in ((2, "AM"), (3, "UNKNOWN")):
        filename = f"hold-{index}.wav"
        wav(tmp_path / filename, 2300 + index * 170)
        doc["recordings"].append({
            "path": filename, "mode": label, "session_id": f"hold-{index}",
            "device": "second synthetic SDR", "frequency_hz": 145500000,
        })
    hold.write_text(json.dumps(doc))

    def fake_observations(rows, model, max_windows, *, accounting=None):
        if accounting is not None:
            accounting.update({"minimum_session_pipeline_coverage": 1.0,
                               "pipeline_coverage": 1.0})
        return [(label,
                 "AM" if label == "UNKNOWN" and session == "hold-3" else label,
                 .99, session, device)
                for _, label, session, device in rows]

    monkeypatch.setattr(gate, "observations", fake_observations)
    report = gate.run(cal, hold, tmp_path, object(),
                      max_far=.60, min_coverage=.50)
    assert report["holdout_diversity_gate_passed"] is True
    assert report["holdout_result"]["unknown_false_accept_rate"] == .50
    assert report["holdout_result"]["unknown_session_macro_false_accept"] == .50
    assert report["holdout_result"]["unknown_worst_device_false_accept_rate"] == 1.0
    assert report["decision"] == "HOLDOUT_FAILED"
    assert report["operationally_validated"] is False


def test_holdout_requires_every_supported_known_mode_in_both_splits(tmp_path, monkeypatch):
    """Synthetic-only: perfect AM cannot substitute for CW/NFM/USB/LSB."""
    import scripts.iq_session_gate as gate
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)
    cal_doc, hold_doc = json.loads(cal.read_text()), json.loads(hold.read_text())
    for i, label in enumerate(("CW", "NFM", "USB", "LSB")):
        for prefix, doc, freq in (
                ("cal", cal_doc, 3700 + 430 * i),
                ("hold", hold_doc, 5700 + 430 * i)):
            filename = f"{prefix}-{label.lower()}.wav"
            wav(tmp_path / filename, freq)
            doc["recordings"].append({
                "path": filename, "mode": label, "session_id": f"{prefix}-0",
                "device": "synthetic device", "frequency_hz": 145500000})
    # Holdout must have 2 known and 2 UNKNOWN sessions, 2 SDRs in each.
    for i, label in ((2, "AM"), (3, "UNKNOWN")):
        filename = f"hold-extra-{i}.wav"
        wav(tmp_path / filename, 8300 + 310 * i)
        hold_doc["recordings"].append({
            "path": filename, "mode": label, "session_id": f"hold-{i}",
            "device": "second synthetic SDR", "frequency_hz": 145500000})
    # Complete the held-out class x SDR matrix, not just aggregate labels.
    # All additional known captures share the second SDR's known session.
    for i, label in enumerate(("CW", "NFM", "USB", "LSB")):
        filename = f"hold-second-{label.lower()}.wav"
        wav(tmp_path / filename, 9400 + i * 210)
        hold_doc["recordings"].append({
            "path": filename, "mode": label, "session_id": "hold-2",
            "device": "second synthetic SDR", "frequency_hz": 145500000})
    cal.write_text(json.dumps(cal_doc))
    hold.write_text(json.dumps(hold_doc))

    def perfect(rows, model, max_windows, *, accounting=None):
        if accounting is not None:
            accounting.update({"minimum_session_pipeline_coverage": 1.0,
                               "pipeline_coverage": 1.0})
        return [(label, label, .99, session, device)
                for _, label, session, device in rows]

    monkeypatch.setattr(gate, "observations", perfect)
    # One session per class x SDR cell is not independent replication,
    # even when every class and SDR is represented.
    single_session = gate.run(cal, hold, tmp_path, object())
    assert single_session["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_DEVICE_SESSION_DIVERSITY"
    assert single_session["holdout_class_device_coverage_gate_passed"] is True
    assert single_session["holdout_class_device_cells_below_min_sessions"] == 12

    # Add a second independent synthetic session for every class x SDR
    # (known modes share one known session per SDR; UNKNOWN stays separate).
    for device_index, device in enumerate(("synthetic device", "second synthetic SDR")):
        for mode_index, label in enumerate(("CW", "AM", "NFM", "USB", "LSB", "UNKNOWN")):
            filename = f"hold-repeat-{device_index}-{label.lower()}.wav"
            wav(tmp_path / filename, 12000 + 180 * (device_index * 6 + mode_index))
            family = "unknown" if label == "UNKNOWN" else "known"
            hold_doc["recordings"].append({
                "path": filename, "mode": label,
                "session_id": f"hold-repeat-{device_index}-{family}",
                "device": device, "frequency_hz": 145500000})
    hold.write_text(json.dumps(hold_doc))
    complete = gate.run(cal, hold, tmp_path, object())
    assert complete["decision"] == "HOLDOUT_EVALUATED"
    assert complete["holdout_class_device_session_diversity_gate_passed"] is True
    assert complete["holdout_class_device_cells_below_min_sessions"] == 0
    assert complete["min_holdout_sessions_per_class_device_cell"] == 2

    # Removing only one session's CW from SDR-B leaves the class x SDR
    # matrix complete, but must fail the independent-session gate.
    extra_cw = next(row for row in hold_doc["recordings"]
                    if row["path"] == "hold-repeat-1-cw.wav")
    hold_doc["recordings"].remove(extra_cw)
    hold.write_text(json.dumps(hold_doc))
    missing_replication = gate.run(cal, hold, tmp_path, object())
    assert missing_replication["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_DEVICE_SESSION_DIVERSITY"
    assert missing_replication["holdout_class_device_coverage_gate_passed"] is True
    assert missing_replication["holdout_class_device_cells_below_min_sessions"] == 1
    hold_doc["recordings"].append(extra_cw)
    hold.write_text(json.dumps(hold_doc))
    assert complete["holdout_class_coverage_gate_passed"] is True
    assert complete["required_known_classes"] == ["CW", "AM", "NFM", "USB", "LSB"]
    assert complete["operationally_validated"] is False
    assert complete["holdout_class_device_coverage_gate_passed"] is True
    assert complete["required_holdout_class_device_cells"] == 12
    assert complete["missing_holdout_class_device_cells"] == 0

    # Every class exists globally and both SDRs have KNOWN/UNKNOWN, yet CW
    # is absent on SDR-B. Previously this incorrectly returned EVALUATED.
    hold_doc["recordings"] = [
        row for row in hold_doc["recordings"]
        if not (row["mode"] == "CW" and row["device"] == "second synthetic SDR")
    ]
    hold.write_text(json.dumps(hold_doc))
    missing_cell = gate.run(cal, hold, tmp_path, object())
    assert missing_cell["holdout_class_coverage_gate_passed"] is True
    assert missing_cell["holdout_diversity_gate_passed"] is True
    assert missing_cell["holdout_class_device_coverage_gate_passed"] is False
    assert missing_cell["missing_holdout_class_device_cells"] == 1
    assert missing_cell["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_DEVICE_COVERAGE"
    assert "second synthetic SDR" not in json.dumps(missing_cell)
    hold_doc["recordings"].append({
        "path": "hold-second-cw.wav", "mode": "CW", "session_id": "hold-2",
        "device": "second synthetic SDR", "frequency_hz": 145500000})
    hold.write_text(json.dumps(hold_doc))

    cal_doc["recordings"] = [r for r in cal_doc["recordings"]
                             if r["mode"] != "CW"]
    cal.write_text(json.dumps(cal_doc))
    missing_cal = gate.run(cal, hold, tmp_path, object())
    assert missing_cal["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_COVERAGE"
    assert missing_cal["missing_known_classes_calibration"] == ["CW"]
    assert missing_cal["missing_known_classes_holdout"] == []

    hold_doc["recordings"] = [r for r in hold_doc["recordings"]
                              if r["mode"] != "USB"]
    hold.write_text(json.dumps(hold_doc))
    missing_both = gate.run(cal, hold, tmp_path, object())
    assert missing_both["decision"] == "HOLDOUT_INSUFFICIENT_CLASS_COVERAGE"
    assert missing_both["missing_known_classes_calibration"] == ["CW"]
    assert missing_both["missing_known_classes_holdout"] == ["USB"]
    assert missing_both["operationally_validated"] is False


def test_end_to_end_gate_rejects_missing_device_identity(tmp_path, monkeypatch):
    import scripts.iq_session_gate as gate
    cal = manifest(tmp_path, "cal.json", "cal", 1200)
    hold = manifest(tmp_path, "hold.json", "hold", 1700)
    def legacy_observations(rows, model, max_windows, *, accounting=None):
        return [(label, label, .99, session) for _, label, session, _ in rows]
    monkeypatch.setattr(gate, "observations", legacy_observations)
    with pytest.raises(ValueError, match="Device metadata required"):
        gate.run(cal, hold, tmp_path, object())


def test_worst_known_class_blocks_cw_failure_masked_by_am_sessions():
    """Synthetic-only: aggregate and device averages cannot conceal failed CW."""
    rows = [("AM", "AM", .99, f"am-{i}", "sdr-a") for i in range(20)]
    rows += [("CW", "AM", .99, "cw-failed", "sdr-a"),
             ("UNKNOWN", "UNKNOWN", .99, "unknown", "sdr-a")]
    measured = rates(rows, .95)
    assert measured["known_session_macro_coverage"] == pytest.approx(20 / 21)
    assert measured["known_worst_device_correct_coverage"] == pytest.approx(20 / 21)
    assert measured["known_worst_class_session_macro_coverage"] == 0.0
    assert measured["known_classes_observed"] == 2
    selected, _ = select(rows, max_far=.10, min_coverage=.50)
    assert selected is None
    assert "cw-failed" not in json.dumps(measured)


def test_worst_known_class_accepts_two_correctly_covered_modes():
    """Synthetic control: class-level guard accepts correctly covered CW and AM."""
    rows = [("AM", "AM", .99, "am-session", "sdr-a"),
            ("CW", "CW", .99, "cw-session", "sdr-b"),
            ("UNKNOWN", "UNKNOWN", .99, "noise-session", "sdr-b")]
    selected, _ = select(rows, max_far=.10, min_coverage=.50)
    assert selected is not None
    assert selected["known_worst_class_session_macro_coverage"] == 1.0
    assert selected["known_classes_observed"] == 2


def test_class_device_cell_blocks_masked_cw_failure():
    """Synthetic: CW fails on SDR-B but both class and SDR marginal rates pass.

    This cross-product guard prevents a Simpson-like false pass. It measures
    only observed cells; missing class/SDR combinations still require RF QA.
    """
    known = ([("CW", "CW", .99, f"cw-a-{i}", "sdr-a") for i in range(10)]
             + [("CW", "AM", .99, "cw-b-failed", "sdr-b")]
             + [("AM", "AM", .99, f"am-b-{i}", "sdr-b") for i in range(20)])
    unknown = [("UNKNOWN", "UNKNOWN", .99, "noise-a", "sdr-a"),
               ("UNKNOWN", "UNKNOWN", .99, "noise-b", "sdr-b")]
    rows = known + unknown
    observed = rates(rows, .95)
    assert observed["known_worst_class_session_macro_coverage"] == pytest.approx(10 / 11)
    assert observed["known_worst_device_correct_coverage"] == pytest.approx(20 / 21)
    assert observed["known_worst_class_device_correct_coverage"] == 0.0
    assert observed["known_class_device_cells_observed"] == 3
    assert observed["unknown_worst_device_false_accept_rate"] == 0.0
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is None
    assert "sdr-a" not in json.dumps(observed)
    assert "sdr-b" not in json.dumps(observed)
    assert "cw-b-failed" not in json.dumps(observed)


def test_class_device_cell_control_and_legacy_rows():
    """Synthetic control: fully correct observed cells pass; legacy rate API stays safe."""
    rows = [("CW", "CW", .99, "cw-a", "sdr-a"),
            ("CW", "CW", .99, "cw-b", "sdr-b"),
            ("AM", "AM", .99, "am-a", "sdr-a"),
            ("AM", "AM", .99, "am-b", "sdr-b"),
            ("UNKNOWN", "UNKNOWN", .99, "noise-a", "sdr-a"),
            ("UNKNOWN", "UNKNOWN", .99, "noise-b", "sdr-b")]
    chosen, _ = select(rows, max_far=.10, min_coverage=.50)
    assert chosen is not None
    assert chosen["known_worst_class_device_correct_coverage"] == 1.0
    assert chosen["known_class_device_cells_observed"] == 4
    legacy = rates([row[:4] for row in rows], .95)
    assert legacy["known_worst_class_device_correct_coverage"] is None
    assert legacy["known_class_device_cells_observed"] is None


@pytest.mark.parametrize("bad_probability", [True, "1.0", np.bool_(True)])
def test_observations_rejects_coerced_softmax_probabilities(tmp_path, bad_probability):
    """Synthetic regression: numeric-looking strings/bools must not pass RF gates."""
    from pt2vhf.dsp.iq_classifier import CLASSES, Classification
    from scripts.iq_session_gate import observations

    source = tmp_path / "synthetic_iq.wav"
    wav(source, 1200)

    class Malformed:
        def predict(self, iq):
            scores = {name: 0.0 for name in CLASSES}
            scores["AM"] = bad_probability
            return Classification("AM", 1.0, scores)

    with pytest.raises(ValueError, match="Invalid model probability values"):
        observations([(source, "AM", "synthetic-session", "synthetic-SDR")],
                     Malformed(), 2)


@pytest.mark.parametrize("valid_probability", [np.float32(1.0), np.float64(1.0)])
def test_observations_accepts_real_numpy_softmax_probabilities(tmp_path, valid_probability):
    """Numeric numpy scalar outputs remain supported by the strict RF gate."""
    from pt2vhf.dsp.iq_classifier import CLASSES, Classification
    from scripts.iq_session_gate import observations

    source = tmp_path / "synthetic_iq.wav"
    wav(source, 1200)

    class Numeric:
        def predict(self, iq):
            scores = {name: 0.0 for name in CLASSES}
            scores["AM"] = valid_probability
            return Classification("AM", 1.0, scores)

    rows = observations([(source, "AM", "synthetic-session", "synthetic-SDR")],
                        Numeric(), 2)
    assert len(rows) == 2
    assert all(row[0] == row[1] == "AM" for row in rows)
