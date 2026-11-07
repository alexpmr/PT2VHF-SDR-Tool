"""Sinais sintéticos para testes (voz SSB com entonação, FM, AM, CW)."""
import numpy as np
from scipy import signal
def voice_ssb(fs=48000, dur=4.0, delta=0.0, snr_db=20, seed=0, lsb=False, f0base=120):
    rng=np.random.default_rng(seed)
    n=int(fs*dur); t=np.arange(n)/fs
    f0=f0base*(1+0.18*np.sin(2*np.pi*0.6*t+rng.uniform(0,6))+0.08*np.sin(2*np.pi*2.3*t))
    ph=2*np.pi*np.cumsum(f0)/fs
    # syllables envelope
    syl=(0.5+0.5*np.sin(2*np.pi*3.5*t+rng.uniform(0,6)))**2
    x=np.zeros(n,complex)
    for k in range(1,40):
        fk=k*f0
        a=np.exp(-((fk-600)/400)**2)+0.6*np.exp(-((fk-1500)/500)**2)+0.3*np.exp(-((fk-2400)/400)**2)
        a=a*(fk<3500)
        x+=a*np.exp(1j*(k*ph+rng.uniform(0,6)))
    x*=syl
    # filtro SSB 300-2800 (analítico)
    taps=signal.firwin(801,1250,fs=fs)*np.exp(2j*np.pi*1550*np.arange(801)/fs)
    x=signal.lfilter(taps,1,x)
    if lsb: x=np.conj(x)
    x=x*np.exp(2j*np.pi*delta*t)
    p=np.mean(np.abs(x)**2); nz=np.sqrt(p/10**(snr_db/10)/2)
    x=x+nz*(rng.normal(size=n)+1j*rng.normal(size=n))
    return x.astype(np.complex64)


FS = 240000


def noise(n, lvl, seed=0):
    r = np.random.default_rng(seed)
    return lvl * (r.normal(size=n) + 1j * r.normal(size=n)) / np.sqrt(2)


def nfm(dur=1.0, off=0, dev=3000):
    t = np.arange(int(FS * dur)) / FS
    m = np.sin(2 * np.pi * 800 * t) + 0.5 * np.sin(2 * np.pi * 1900 * t)
    return np.exp(1j * 2 * np.pi * np.cumsum(off + dev * m) / FS)


def wfm(dur=1.0):
    t = np.arange(int(FS * dur)) / FS
    m = sum(np.sin(2 * np.pi * f * t) for f in (300, 1200, 5000, 9000)) / 2
    return np.exp(1j * 2 * np.pi * np.cumsum(50000 * m) / FS)


def am(dur=1.0):
    t = np.arange(int(FS * dur)) / FS
    return 1 + 0.6 * np.sin(2 * np.pi * 700 * t) + 0.3 * np.sin(2 * np.pi * 2300 * t)


def cw(dur=1.0):
    t = np.arange(int(FS * dur)) / FS
    key = (np.sin(2 * np.pi * 6 * t) > 0).astype(float)
    return np.convolve(key, np.hanning(480) / 240, "same").astype(complex)


def ssb240(dur=2.0, delta=0, lsb=False):
    return signal.resample_poly(voice_ssb(fs=48000, dur=dur, delta=delta, snr_db=40, lsb=lsb), 5, 1)
