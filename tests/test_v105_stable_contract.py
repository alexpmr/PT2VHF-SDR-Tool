"""Release 1.0.5: preserve features already proven on the 1.0.4 CI SHA.

These assertions prevent a version-only consolidation from accidentally
dropping verified functionality. They do not claim actual RF hardware QA.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path


def test_version_matches_package_metadata():
    from pt2vhf import APP_NAME, __version__

    root = Path(__file__).resolve().parents[1]
    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M)
    assert match is not None
    assert match.group(1) == __version__
    assert tuple(map(int, __version__.split("."))) >= (1, 0, 5)
    assert APP_NAME == "PT2VHF SDR Tool"


def test_approved_source_backends_remain_exposed():
    from pt2vhf.sources.mirics import SOURCE_NAME, is_rsp_device
    from pt2vhf.ui.panels import SOURCES, ReceiverPanel

    assert SOURCE_NAME in SOURCES
    assert "RTL-SDR" in SOURCES and "rtl_tcp" in SOURCES
    assert "SoapySDR" in SOURCES and "Arquivo IQ" in SOURCES
    assert is_rsp_device({"driver": "sdrplay"})
    assert is_rsp_device({"driver": "sdrplay3"})
    assert is_rsp_device({"driver": "miri"})
    assert not is_rsp_device({"driver": "rtlsdr"})
    assert callable(ReceiverPanel.show_rsp_diagnostics)


def test_ota_probe_mode_and_ui_preserved():
    from pt2vhf import updater
    from pt2vhf.ui.assist_panels import UpdateController
    from pt2vhf.ui.settings_panel import SettingsPanel

    assert "probe_only" in inspect.signature(updater.apply).parameters
    assert callable(UpdateController.probe_helper)
    assert "testOtaHelper" in SettingsPanel.__dict__
    # Installer scripts are part of the validated setup, not optional.
    script = (Path(__file__).resolve().parents[1] / "scripts" /
              "apply-update.ps1").read_text(encoding="utf-8")
    assert "ProbeOnly" in script
    assert "ReadyFile" in script


def test_rs41_diagnostic_is_noninvasive_and_remains_available():
    from pt2vhf.ui.sonde_decoder_panel import SondeDecoderPanel

    assert callable(SondeDecoderPanel.verify_tools)
    assert callable(SondeDecoderPanel.copy_diagnostics)
    assert callable(SondeDecoderPanel._locate_decoder)


def test_approved_waterfall_and_display_interfaces_remain_available():
    from pt2vhf.ui.waterfall import SpectrumWaterfall
    from pt2vhf.ui.display_settings import DisplaySettings
    from pt2vhf.ui.resource_meter import ResourceMeter

    assert hasattr(SpectrumWaterfall, "centerTuneRequested")
    assert callable(SpectrumWaterfall.center_on_vfo)
    assert callable(DisplaySettings.__init__)
    assert callable(ResourceMeter.__init__)


def test_neural_iq_model_not_promoted_into_stable_release():
    # This PR still requires independently labeled RF data. Prevent source
    # tree leakage of its experimental classifier into stable packages.
    root = Path(__file__).resolve().parents[1]
    assert not (root / "pt2vhf" / "dsp" / "iq_classifier.py").exists()
