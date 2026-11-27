# Inventário — PT2VHF-SDR-Tool

> Gerado pelo **Scout** (Reversa) em 2026-11-27, a partir da branch do PR #32 (base `c118eff`, v0.13.3).
> Escala: 🟢 CONFIRMADO (lido no código) · 🟡 INFERIDO · 🔴 LACUNA

## Visão geral

| Item | Valor |
|------|-------|
| Tipo | Aplicação desktop de recepção SDR (radioamador), somente RX 🟢 |
| Linguagem principal | Python ≥ 3.10 (CI em 3.12) 🟢 |
| UI | PySide6 6.11.3 (Qt 6) + pyqtgraph 🟢 |
| DSP | NumPy + SciPy 🟢 |
| Versão no código | 0.13.3 (`pyproject.toml`, `pt2vhf/__init__.py`) 🟢 |
| Arquivos versionados (sem `.claude/`, `.agents/`, `.reversa/`) | 133 🟢 |
| Linhas Python em `pt2vhf/` | ~14.0 mil (58 arquivos) 🟢 |
| Linhas de teste em `tests/` | ~2,8 mil (24 arquivos `test_*.py`) 🟢 |
| Banco de dados | Nenhum. Persistência em JSON/CSV no diretório de configuração 🟢 |
| Containers | Nenhum `Dockerfile`/compose 🟢 |
| Entrega binária | Windows x64: PyInstaller (pasta + portátil) e Inno Setup 6 🟢 |

## Linguagens e arquivos

| Extensão | Qtde | Observação |
|----------|-----:|------------|
| `.py` | 90 | código, testes, scripts e empacotamento |
| `.md` | 17 | README, BACKLOG, CHANGELOG, CLAUDE e notas de release |
| `.png` | 11 | screenshots e mockups em `docs/` |
| `.yml` | 3 | workflows do GitHub Actions |
| `.ps1` | 3 | scripts OTA para Windows |
| `.txt` | 3 | requirements e `version_info.txt` |
| `.toml`, `.spec`, `.iss`, `.ico` | 1 cada | pyproject, PyInstaller, Inno Setup, ícone |

## Árvore de pastas

```
.
├── .github/workflows/   build.yml, release.yml, verify-site.yml
├── docs/                notas de release (0.6.0 → 0.13.3), BUILD_*.md, screenshots
├── packaging/           installer.iss, make_version_info.py, version_info.txt, ícones
├── pt2vhf/              pacote da aplicação
│   ├── sources/         aquisição IQ (RTL-SDR, rtl_tcp, SoapySDR, simulador, WAV IQ)
│   ├── dsp/             filtros, demodulação, receptor, efeitos de áudio, assistente
│   ├── decoders/        AFSK 1200, AX.25, APRS, DTMF/CTCSS
│   └── ui/              janela principal, LCD, waterfall, painéis
├── scripts/             run_tests.py, verify_site.py, scripts OTA .ps1
├── tests/               pytest + sinais sintéticos
├── run_pt2vhf.py        lançador
├── pt2vhf.spec          PyInstaller
└── build_windows.bat    atalho de build local
```

## Módulos funcionais

Agrupamento lógico usado como unidade de análise para o Arqueólogo. 🟡 (agrupamento inferido; arquivos 🟢)

| Módulo | Arquivos | Linhas | Responsabilidade |
|--------|----------|-------:|------------------|
| `sources` | `sources/base.py`, `rtlsdr_source.py`, `rtl_driver.py`, `network_sources.py`, `sim_sources.py` | ~1.280 | Interface comum de fonte IQ; RTL-SDR USB robusto, preparação de driver WinUSB no Windows, rtl_tcp, SoapySDR, simulador e arquivo WAV IQ |
| `dsp` | `dsp/filters.py`, `demod.py`, `receiver.py`, `audiofx.py`, `assist.py` | ~1.000 | Decimação/canalização, demoduladores (AM/FM/SSB etc.), AGC, noise blanker, squelch, EQ/notch/NR, assistente de sintonia |
| `decoders` | `decoders/afsk.py`, `ax25.py`, `aprs.py`, `tones.py` | ~660 | Modem Bell 202, quadros AX.25/HDLC/FCS, parser APRS (incl. Mic-E), DTMF e CTCSS por Goertzel |
| `engine` | `engine.py`, `audio.py`, `timeshift.py` | ~770 | Thread de processamento fonte → DSP → áudio/decoders, saída PortAudio, gravação WAV, buffer circular de IQ ("voltar no tempo") |
| `scanner` | `scanner.py`, `occupancy.py` | ~450 | Varredura por espectro (FFT), saltos entre segmentos, histórico de ocupação 24 h |
| `memory` | `memory.py`, `memory_regions.py`, `presets.py`, `config.py` | ~560 | Memórias de canais e categorias, CSV CHIRP, perfis regionais, memórias prontas, configuração JSON persistente |
| `traffic` | `traffic.py`, `sonde_rx.py`, `aprs_map.py`, `aprs_igate.py`, `satellites.py` | ~1.100 | ADS-B/AIS/sondas por feeds externos, RS41 via `fsk_demod`/`rs41mod`, mapa Leaflet, iGate APRS-IS somente RX, SGP4/Doppler por TLE |
| `ai_audio` | `neural_audio.py`, `live_caption.py`, `transcribe.py` | ~370 | RNNoise e faster-whisper locais (legendas e transcrição) |
| `integrations` | `webserver.py`, `rigctl.py`, `updater.py` | ~650 | Painel web local/LAN com áudio, CAT via Hamlib `rigctld`, OTA do site oficial |
| `ui` | `ui/*.py` (17 arquivos) + `i18n.py` | ~7.000 | Janela principal (2.371 linhas), LCD, waterfall com clique para sintonizar, abas e painéis, idiomas |
| `app` | `app.py`, `__main__.py`, `run_pt2vhf.py` | ~200 | Argumentos de linha de comando, selftest, screenshot, inicialização |

## Pontos de entrada 🟢

| Caminho | Tipo |
|---------|------|
| `run_pt2vhf.py` | lançador de script |
| `pt2vhf/__main__.py` | `python -m pt2vhf` |
| `pt2vhf/app.py:main` | `main()` com argparse: `--debug`, `--sim`, `--screenshot PNG`, `--selftest` |
| `pyproject.toml` → `pt2vhf-sdr` | gui-script |
| `pt2vhf.spec` | executável PyInstaller |

## Configuração 🟢

- `pt2vhf/config.py`: JSON em `%APPDATA%\PT2VHF-SDR-Tool` (Windows) ou `~/.config/PT2VHF-SDR-Tool`.
- Variáveis de ambiente usadas em teste: `QT_QPA_PLATFORM=offscreen`, `PT2VHF_NO_AUTOCONNECT=1`, `PT2VHF_NO_STARTUP_DIALOGS=1`.
- Não há `.env.example`.

## CI/CD 🟢

| Workflow | Gatilho | O que faz |
|----------|---------|-----------|
| `build.yml` ("Testes (build Windows sob demanda)") | push/PR; job Windows só em `workflow_dispatch` com `build_windows`, PR de `release/stable-*`/`fix/ota-*` ou commit com `[build-windows]` | Testes Linux Qt offscreen (container Playwright); no Windows: testes, smoke OTA, drivers RTL-SDR Blog/libwdi, PyInstaller, autoteste dos .exe, Inno Setup, instalação silenciosa, SHA-256, artefatos e GitHub Release |
| `release.yml` | `workflow_dispatch` | Promove build Windows aprovado (run_id + versão) |
| `verify-site.yml` | `workflow_dispatch` | `scripts/verify_site.py` contra o site público |

## Integrações externas 🟢

| Integração | Onde | Natureza |
|------------|------|----------|
| `www.pt2vhf.com` (OTA, `/sdr`) | `updater.py`, `ui/main_window.py` | HTTPS, manifesto + SHA-256 |
| dump1090/readsb, NMEA AIS, JSON de sondas | `traffic.py` | feeds locais/externos (não é demodulação RF nativa) |
| `fsk_demod` / `rs41mod` | `sonde_rx.py` | subprocessos sem shell, desativado por padrão |
| APRS-IS | `aprs_igate.py` | TCP, RF → IS, exige passcode e ação explícita |
| Hamlib `rigctld` | `rigctl.py` | TCP 4532 |
| Leaflet (unpkg) e tiles OpenStreetMap | `aprs_map.py`, `traffic.py` | HTML exportado |
| PowerShell / libwdi | `sources/rtl_driver.py` | preparação do driver WinUSB no Windows |
| Servidor HTTP próprio | `webserver.py` | local/LAN, sem TLS |

## Dados e persistência 🟢

Sem banco de dados. Arquivos: configuração JSON, memórias em CSV (formato CHIRP), exportações CSV/GPX/KML/HTML de tráfego, WAV de gravações, legendas exportadas. Detalhar com o `reversa-data-master` só se necessário.

## Testes 🟢

- Framework: pytest (≥ 8); `tests/conftest.py` mantém QApplication única.
- 24 arquivos `test_*.py`, ~2,8 mil linhas; sinais sintéticos em `tests/synth_signals.py`.
- Execução recomendada: `QT_QPA_PLATFORM=offscreen python -X faulthandler scripts/run_tests.py`.
- Cobertura por linha: 🔴 LACUNA (não há relatório de cobertura configurado).
- Muitos testes são nomeados por versão (`test_v030_features.py` … `test_v090_*`), não por módulo 🟢.

## Observações para as próximas fases

- `ui/main_window.py` (2.371 linhas) e `ui/panels.py` (1.101) concentram boa parte da lógica de UI; candidatos a análise aprofundada 🟡.
- RS41, ADS-B/AIS e IA de áudio têm estados distintos (implementado ≠ homologado) registrados no `CLAUDE.md`; as specs devem refletir isso 🟢.
- `.claude/skills/` e `.agents/skills/` (Reversa + impeccable) foram excluídos do inventário por serem ferramentas, não produto 🟢.
