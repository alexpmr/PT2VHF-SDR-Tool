# SDRplay RSP1 / MSI-SDR — experimental support in PT2VHF SDR Tool v1.0.2

This release adds a **receiver selection and control path**, not certified USB
plug-and-play. The Windows package's normal RTL-SDR and other source features
remain available. A real RSP1/Mirics receiver and native SoapySDR modules
are required to receive RF using this option.

## Driver choices

1. **SDRplay API**: SDRplay Hardware API 3.x on Windows **plus** SoapySDR and
   SoapySDRPlay3 (`driver=sdrplay` or `sdrplay3`). Current upstream
   SoapySDRPlay3 documentation requires SDRplay API >= 3.15:
   https://github.com/pothosware/SoapySDRPlay3
   Official SDRplay API: https://sdrplay.com/hardware-api/
2. **Mirics**: SoapySDR and SoapyMiri / libmirisdr
   (`driver=miri`, `soapymiri`, `mirisdr`):
   https://github.com/ericek111/SoapyMiri

A receiver marketed as "RSP1" or "MSI-SDR" does **not** prove compatibility
with the SDRplay API. Device identification is by a successfully enumerated
SoapySDR driver key, never just by USB model labels or marketing copy.
The app offers separate SDRplay and Mirics choices if both are discovered.

## Use

- First make sure your current Windows USB driver works in a known receiver
  application. Do not change a working driver to test the PT2VHF app.
- With the appropriate SoapySDR Python binding and native module accessible
  to this app, open **Fonte -> SDRplay / MSi-SDR (RSP)**.
- Click refresh, select the discovered backend and click **Ligar**.
- Initial rate is 2.4 MS/s, **not** a claim that every RSP variant supports it.
  No device/driver found? Run `SoapySDRUtil --find` externally and send the
  results, Windows 10/11 revision, installed native driver version, and USB
  VID/PID in an issue. The packaged exe cannot automatically import Python
  packages installed into an unrelated Python environment.

## Current limitations

- The RSP native SoapySDR/SDRplay/Mirics libraries are **not bundled** into
  this Windows installer. The official SDRplay API has separate licensing and
  installation requirements. SoapyMiri on Windows may require building.
- No automatic USB driver installation or replacement; the app never
  downloads or executes Zadig for this RSP source.
- No physical hardware IQ streaming, RF range, ADC resolution, temperature,
  gain or long-run Windows stability tests have been completed for this device.
- IQ/ONNX neural classifier is not part of this release.
- Splash artwork remains the existing text fallback until the approved
  original PT2VHF artwork is available.

## Acceptance checklist before claiming plug-and-play

1. Identified VID/PID and confirmed the matching native Windows backend.
2. Compatible Soapy Python binding and driver module packaged and verified
   in **both** Setup and Portable builds, plus licensing review.
3. Real RF tests in HF, 2 m, 433 and 915 MHz using actual device capabilities.
4. Stable reconnect/disconnect behavior, correct RF gain, AGC and IQ streams.
5. No regressions to RTL-SDR, OTA, Windows Setup and Portable.

This documentation intentionally separates successful *software CI tests* from
physical SDR validation. The public app should not promise automatic operation
without the external dependencies and hardware tests above.
