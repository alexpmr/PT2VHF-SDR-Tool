"""MSi2500/MSi001 SDR (generic RSP1 clones) detection via external Soapy drivers.

Supported Soapy modules commonly identify as driver=miri or driver=soapyMiri.
This feature does not bundle SoapySDR/USB drivers or claim SDRplay API
compatibility. Hardware may require a one-time vendor-independent driver setup.
"""
from __future__ import annotations

MIRICS_DRIVERS = frozenset(("miri", "soapymiri", "mirisdr"))
SOURCE_NAME = "MSi-SDR (RSP1 clone)"
MISSING_DRIVER = (
    "MSi-SDR não detectado via SoapySDR. Este receptor MSi2500/MSi001 "
    "não usa o driver RTL-SDR e pode não ser compatível com a API oficial SDRplay. "
    "Instale um módulo SoapySDR para Mirics (driver=miri ou driver=soapyMiri), "
    "verifique com 'SoapySDRUtil --find' e selecione o dispositivo. "
    "Não substitua automaticamente o driver USB de outros receptores."
)


def is_mirics_device(device) -> bool:
    """Trust explicit Soapy driver identifiers, not an ambiguous product name."""
    try:
        props = {str(k).lower(): str(v).strip().lower() for k, v in dict(device).items()}
    except (TypeError, ValueError):
        return False
    return props.get("driver", "") in MIRICS_DRIVERS


def enumerate_mirics(enumerate_fn=None) -> list[str]:
    """Return only Mirics-capable Soapy descriptors, without USB driver changes."""
    if enumerate_fn is None:
        try:
            import SoapySDR
        except ImportError:
            return []
        enumerate_fn = SoapySDR.Device.enumerate
    try:
        return [
            ",".join(f"{k}={v}" for k, v in dict(dev).items())
            for dev in enumerate_fn()
            if is_mirics_device(dev)
        ]
    except Exception:
        # Device detection should not abort GUI startup if the module is absent.
        return []
