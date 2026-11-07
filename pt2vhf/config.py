"""Configurações persistentes do usuário (JSON em %APPDATA%\\PT2VHF-SDR-Tool)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "PT2VHF-SDR-Tool"


DEFAULTS = {
    "source": "Simulador",
    "device_index": 0,
    "rtl_tcp_host": "127.0.0.1",
    "rtl_tcp_port": 1234,
    "soapy_args": "",
    "sample_rate": 1_200_000,
    "center_freq": 145.5e6,
    "vfo_freq": 145.570e6,
    "vfo_b_freq": 145.430e6,
    "mode": "NFM",
    "bandwidth": 12000,
    "step": 12500,
    "gain": 30.0,  # None = AGC do sintonizador
    "ppm": 0,
    "bias_tee": False,
    "direct_sampling": 0,
    "volume": 0.5,
    "squelch": -150.0,
    "agc": True,
    "agc_speed": "Médio",
    "nb": False,
    "nr": False,
    "eq_enabled": False,
    "eq_gains": [0, 0, 0, 0, 0, 0, 0, 0],
    "wfm_deemph_us": 75,
    "fft_size": 4096,
    "wf_min_db": -110.0,
    "wf_max_db": -40.0,
    "wf_colormap": "Kiwi",
    "wf_speed": 20,
    "spectrum_avg": 0.5,
    "lcd_theme": "Âmbar",
    "audio_device": None,
    "s_meter_cal": 0.0,
    "my_locator": "GG66qk",
    "my_callsign": "PT2VHF",
    "decoders": {"aprs": True, "dtmf": True, "ctcss": True},
    "scan_dwell_ms": 150,
    "scan_resume_s": 3.0,
    "timeshift_s": 20,
    "check_updates": True,
    "reconnect_on_start": True,
    "rx_was_on": False,
    "device_name": "",
    "web_require_key": False,
    "presentation": False,
    "presentation_minimal": True,
    "recordings_dir": str(Path.home() / "PT2VHF-Gravacoes"),
}


class Config(dict):
    def __init__(self, path: Path | None = None):
        super().__init__(json.loads(json.dumps(DEFAULTS)))
        self.path = path or (config_dir() / "config.json")
        if self.path.exists():
            try:
                self.update(json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
