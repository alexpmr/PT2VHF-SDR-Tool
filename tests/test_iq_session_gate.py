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
