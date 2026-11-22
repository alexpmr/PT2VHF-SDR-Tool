# PT2VHF SDR Tool v1.0.5 — Stable CI-verified consolidation

This is a **consolidation** of the previously approved v1.0.4 Windows release,
not a claim that the backlog is completely implemented. The code is forked from
the exact v1.0.4 GitHub Release commit
`e10865f87959379c0424551b64609333866753f8`.

## Included without modification to their approved behavior

- RTL-SDR, rtl_tcp, SoapySDR, simulator and WAV IQ sources.
- Bands/modes, waterfall tuning and double-click-to-center, LCD/scale and
  resource meter, external upconverter frequency compensation and UI state.
- SDRplay API / SoapySDRPlay3 and Mirics / SoapyMiri RSP discovery and
  backend distinction, with a safe diagnostics button.
- OTA update/download verification, the Windows PowerShell spawn/READY
  handshake and its no-install diagnostic from Help and Settings.
- RS41 workflow using existing external `fsk_demod` and `rs41mod` decoder
  programs, with dependency verification and copyable diagnostics.
- Existing RNNoise and local speech transcription features and UI controls.
- Preserved settings/memory paths; no wipe or forced driver change.

## Tests and evidence

Previously released v1.0.4 passed 248 Linux/Qt tests and Windows tests, both
packaged executable selftests, native OTA helper probe, silent Setup install,
and Setup/Portable OTA smoke. CI run:
https://github.com/alexpmr/PT2VHF-SDR-Tool/actions/runs/43945630719

The v1.0.5 candidate additionally contains
`tests/test_v105_stable_contract.py`: version metadata parity and
regressions for approved interfaces/backends. **Do not announce this version
as validated/published until the exact v1.0.5 commit passes Windows and Linux
CI, the Setup and Portable artifacts are hash-verified, and GitHub Release is
live.** Site/OTA deployment must be verified independently at the Hostinger
`updates.json` and `update.php?product=sdr` endpoints.

## Not included / not yet homologated

- IQ/ONNX classifier is a separate experimental PR #2. Synthetic tests do
  not prove RF real-world accuracy, OOD, WFM or production stability.
- Receiver RSP1/MSi-SDR USB/native Soapy libraries are **not bundled**, and
  actual SDRplay/Mirics RF reception is not field-validated. Detection does
  not mean plug and play.
- RS41 real RF IQ to decoded telemetry remains unproven; fsk_demod and
  rs41mod must be supplied separately.
- Windows crash #8 remains open pending prolonged real-device soak tests.
- Windows OTA #18 remains open pending a genuine inter-version update on
  the user's own machine. A simulator or native helper probe does not close it.
- No Linux/macOS packages or GUI splash graphic are asserted as completed.

The version deliberately avoids speculative changes to DSP, USB drivers,
installer permissions or neural inference while these acceptance gates remain.
