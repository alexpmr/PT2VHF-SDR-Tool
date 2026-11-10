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

    def perfect_observations(rows, model, max_windows):
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
    diverse = gate.run(cal, hold, tmp_path, object())
    assert diverse["decision"] == "HOLDOUT_EVALUATED"
    assert diverse["holdout_diversity_gate_passed"] is True
    assert diverse["distinct_holdout_devices"] == 2
    assert diverse["operationally_validated"] is False
