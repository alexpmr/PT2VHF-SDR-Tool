# Dependências — PT2VHF-SDR-Tool

> Gerado pelo **Scout** (Reversa) em 2026-11-27. Fontes: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, imports em `pt2vhf/`.

Gerenciador: **pip** (setuptools ≥ 68 como backend). Não há lockfile; versões são mínimas, exceto as fixadas. 🟢

## Execução

| Pacote | Restrição | Uso | Fixada? |
|--------|-----------|-----|---------|
| numpy | ≥ 1.26 | DSP, IQ, FFT | não |
| scipy | ≥ 1.11 | filtros, reamostragem | não |
| PySide6 | == 6.11.3 | UI Qt 6 | **sim** |
| pyqtgraph | ≥ 0.13.3 | espectro/waterfall | não |
| sounddevice | ≥ 0.4.6 | áudio via PortAudio | não |
| pyrtlsdr[lib] | ≥ 0.3.0 | RTL-SDR USB (traz librtlsdr) | não |
| sgp4 | ≥ 2.23 | previsão de satélites por TLE | não |
| pyrnnoise | == 0.4.5 | RNNoise | **sim** |
| faster-whisper | ≥ 1.2, < 2.0 | legendas/transcrição local | faixa |

## Desenvolvimento

| Pacote | Restrição | Uso |
|--------|-----------|-----|
| pytest | ≥ 8 | testes |
| pyinstaller | ≥ 6.3 | executável Windows |

## Opcionais em tempo de execução (não declaradas no pyproject) 🟢

| Dependência | Uso | Observação |
|-------------|-----|------------|
| SoapySDR (bindings Python) | `sources/network_sources.py` | importado só quando a fonte é escolhida |
| `fsk_demod`, `rs41mod` | `sonde_rx.py` | binários externos localizados com `shutil.which` |
| Hamlib `rigctld` | `rigctl.py` | daemon externo via TCP |
| dump1090/readsb | `traffic.py` | feed externo |
| PowerShell, libwdi `wdi-simple` | `sources/rtl_driver.py`, CI | só Windows |
| Inno Setup 6 | `packaging/installer.iss` | só build Windows |

## Biblioteca padrão mais usada

`threading`, `queue`, `json`, `logging`, `pathlib`, `dataclasses`, `socket`, `http`, `urllib`, `subprocess`, `csv`, `wave`. 🟢

## Riscos observados 🟡

- Sem lockfile: builds podem variar com versões novas de numpy/scipy/pyqtgraph.
- `faster-whisper` puxa `ctranslate2`/`onnxruntime` indiretamente; impacto no tamanho do instalador não verificado 🔴.
- Dependências opcionais (SoapySDR, rs41mod) não aparecem no `pyproject`, então o `--selftest` é a única verificação.
