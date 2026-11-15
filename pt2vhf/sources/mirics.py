"""RSP1-like receiver discovery with SDRplay API and Mirics alternatives.

The SDRplay API is accessed *through* the optional SoapySDRPlay3 plugin; it is
not imported/bundled here. The Mirics path uses an optional SoapyMiri/libmirisdr
driver. Actual compatibility is established by successful driver enumeration,
never inferred from USB appearance or a label containing RSP1.
"""
from __future__ import annotations

MIRICS_DRIVERS = frozenset(("miri", "soapymiri", "mirisdr"))
SDRPLAY_DRIVERS = frozenset(("sdrplay", "sdrplay3"))
SOURCE_NAME = "MSi-SDR (RSP1 clone)"
MISSING_DRIVER = (
    "Nenhum receptor RSP1/MSi-SDR foi reconhecido pelos módulos SoapySDR. "
    "Há duas opções: SDRplay API com módulo SoapySDRPlay3 (se o dispositivo "
    "for realmente compatível), ou driver Mirics com módulo SoapyMiri/libmirisdr. "
    "Instale apenas o driver que funciona com o seu hardware; verifique com "
    "'SoapySDRUtil --find'. Não substitua automaticamente o driver USB."
)


def _props(device) -> dict[str, str]:
    try:
        return {str(k).strip().lower(): str(v).strip().lower()
                for k, v in dict(device).items()}
    except (TypeError, ValueError):
        return {}


def device_backend(device) -> str:
    """Identify the Soapy backend from the driver key, never from product labels."""
    driver = _props(device).get("driver", "")
    if driver in SDRPLAY_DRIVERS:
        return "SDRplay API"
    if driver in MIRICS_DRIVERS:
        return "Mirics"
    return ""


def is_mirics_device(device) -> bool:
    return device_backend(device) == "Mirics"


def is_sdrplay_device(device) -> bool:
    return device_backend(device) == "SDRplay API"


def is_rsp_device(device) -> bool:
    return bool(device_backend(device))


def _enumerate(enumerate_fn):
    if enumerate_fn is None:
        try:
            import SoapySDR
        except (ImportError, OSError):
            return []
        enumerate_fn = SoapySDR.Device.enumerate
    try:
        return list(enumerate_fn())
    except Exception:
        # Soapy plugins may be unavailable or a device may be disconnected.
        return []


def enumerate_mirics(enumerate_fn=None) -> list[str]:
    """Backward-compatible Mirics-only descriptors for existing clients."""
    return [
        ",".join(f"{k}={v}" for k, v in dict(dev).items())
        for dev in _enumerate(enumerate_fn)
        if is_mirics_device(dev)
    ]


def enumerate_rsp_devices(enumerate_fn=None) -> list[tuple[str, str]]:
    """Return (display_label, Soapy_args) for detected RSP backends.

    If both backend drivers detect the same physical device, both entries are
    deliberately offered. Selection of a driver remains explicit and no
    driver changes/installs are ever made by device discovery.
    """
    devices = []
    for dev in _enumerate(enumerate_fn):
        backend = device_backend(dev)
        if not backend:
            continue
        props = dict(dev)
        descriptor = ",".join(f"{k}={v}" for k, v in props.items())
        desc = str(props.get("label") or props.get("serial") or props.get("hardware") or "RSP")
        devices.append((f"{backend} — {desc}", descriptor))
    return devices
