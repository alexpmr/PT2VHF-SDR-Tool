"""Portable CPU reproducibility controls; synthetic training only, no RF data."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("torch")
ROOT = Path(__file__).resolve().parents[1]
PROBE = (
    "import json,sys;"
    "sys.path.insert(0,'scripts');"
    "from train_iq_unknown_v4 import configure_training_runtime;"
    "print('CPU_POLICY='+json.dumps(configure_training_runtime(True)))"
)


def test_portable_cpu_policy_sets_deterministic_controls():
    env = os.environ.copy()
    env.update(ATEN_CPU_CAPABILITY="default", MKL_CBWR="COMPATIBLE")
    run = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=45, check=True)
    line = next(line for line in run.stdout.splitlines() if line.startswith("CPU_POLICY="))
    policy = json.loads(line.split("=", 1)[1])
    assert policy["portable_cpu"] is True
    assert policy["threads"] == 1
    assert policy["mkldnn_enabled"] is False
    assert policy["deterministic_algorithms"] is True
    assert policy["aten_cpu_capability"] == "default"
    assert policy["mkl_cbwr"] == "COMPATIBLE"


def test_portable_cpu_policy_rejects_missing_preimport_baseline():
    env = os.environ.copy()
    env.pop("ATEN_CPU_CAPABILITY", None)
    env["MKL_CBWR"] = "COMPATIBLE"
    run = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=45)
    assert run.returncode != 0
    assert "ATEN_CPU_CAPABILITY=default" in run.stderr
