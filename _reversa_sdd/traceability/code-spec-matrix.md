# Matriz código × spec

Gerada pelo Redator: cada arquivo do legado versionado e a unit que o especifica. Escala: 🟢 coberto · 🟡 coberto parcialmente ou por inferência · 🔴 sem spec · n/a fora do escopo funcional.

Cobertura: 87 de 87 arquivos funcionais (100%); 12 arquivos n/a (empacotamento, CI e `__init__` de pacote).

| Arquivo do legado | Unit correspondente | Cobertura |
|---|---|---|
| `.github/workflows/build.yml` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `.github/workflows/release.yml` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `.github/workflows/verify-site.yml` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `packaging/installer.iss` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `packaging/make_version_info.py` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `packaging/version_info.txt` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `pt2vhf.spec` | — build/CI/publicação, ver architecture.md e adrs | n/a |
| `pt2vhf/__init__.py` | transversal (`__version__`), ver architecture.md | 🟢 |
| `pt2vhf/__main__.py` | idiomas-e-configuracoes (ponto de entrada `python -m pt2vhf`) | 🟢 |
| `pt2vhf/app.py` | [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md), [legendas-e-transcricao](../legendas-e-transcricao/requirements.md) | 🟢 |
| `pt2vhf/aprs_igate.py` | [igate-aprs](../igate-aprs/requirements.md) | 🟢 |
| `pt2vhf/aprs_map.py` | [aprs-packet](../aprs-packet/requirements.md) | 🟢 |
| `pt2vhf/audio.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md), [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md) | 🟢 |
| `pt2vhf/config.py` | [atualizacao-ota](../atualizacao-ota/requirements.md), [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md) | 🟢 |
| `pt2vhf/decoders/__init__.py` | — (pacote Python) | n/a |
| `pt2vhf/decoders/afsk.py` | [aprs-packet](../aprs-packet/requirements.md) | 🟢 |
| `pt2vhf/decoders/aprs.py` | [aprs-packet](../aprs-packet/requirements.md), [satelites](../satelites/requirements.md) | 🟢 |
| `pt2vhf/decoders/ax25.py` | [aprs-packet](../aprs-packet/requirements.md) | 🟢 |
| `pt2vhf/decoders/tones.py` | [tons-dtmf-ctcss](../tons-dtmf-ctcss/requirements.md) | 🟢 |
| `pt2vhf/dsp/__init__.py` | — (pacote Python) | n/a |
| `pt2vhf/dsp/assist.py` | [assistente-de-sintonia](../assistente-de-sintonia/requirements.md) | 🟢 |
| `pt2vhf/dsp/audiofx.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md) | 🟢 |
| `pt2vhf/dsp/demod.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md), [display-e-instrumentos](../display-e-instrumentos/requirements.md) | 🟢 |
| `pt2vhf/dsp/filters.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md) | 🟢 |
| `pt2vhf/dsp/receiver.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md), [espectro-e-waterfall](../espectro-e-waterfall/requirements.md) | 🟢 |
| `pt2vhf/engine.py` | [aprs-packet](../aprs-packet/requirements.md), [assistente-de-sintonia](../assistente-de-sintonia/requirements.md), [demodulacao-e-audio](../demodulacao-e-audio/requirements.md), [espectro-e-waterfall](../espectro-e-waterfall/requirements.md), [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md), [radiossonda-rs41](../radiossonda-rs41/requirements.md), [recepcao-sdr](../recepcao-sdr/requirements.md), [reducao-de-ruido-neural](../reducao-de-ruido-neural/requirements.md), [tons-dtmf-ctcss](../tons-dtmf-ctcss/requirements.md) | 🟢 |
| `pt2vhf/i18n.py` | [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md) | 🟢 |
| `pt2vhf/live_caption.py` | [legendas-e-transcricao](../legendas-e-transcricao/requirements.md) | 🟢 |
| `pt2vhf/memory.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md) | 🟢 |
| `pt2vhf/memory_regions.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md) | 🟢 |
| `pt2vhf/neural_audio.py` | [reducao-de-ruido-neural](../reducao-de-ruido-neural/requirements.md) | 🟢 |
| `pt2vhf/occupancy.py` | [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `pt2vhf/presets.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md) | 🟢 |
| `pt2vhf/rigctl.py` | [cat-rigctl](../cat-rigctl/requirements.md) | 🟢 |
| `pt2vhf/satellites.py` | [satelites](../satelites/requirements.md) | 🟢 |
| `pt2vhf/scanner.py` | [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `pt2vhf/sonde_rx.py` | [radiossonda-rs41](../radiossonda-rs41/requirements.md) | 🟢 |
| `pt2vhf/sources/__init__.py` | — (pacote Python) | n/a |
| `pt2vhf/sources/base.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `pt2vhf/sources/network_sources.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `pt2vhf/sources/rtl_driver.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `pt2vhf/sources/rtlsdr_source.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `pt2vhf/sources/sim_sources.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `pt2vhf/timeshift.py` | [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md) | 🟢 |
| `pt2vhf/traffic.py` | [radiossonda-rs41](../radiossonda-rs41/requirements.md), [trafego-adsb-ais](../trafego-adsb-ais/requirements.md) | 🟢 |
| `pt2vhf/transcribe.py` | [legendas-e-transcricao](../legendas-e-transcricao/requirements.md) | 🟢 |
| `pt2vhf/ui/__init__.py` | — (pacote Python) | n/a |
| `pt2vhf/ui/analog.py` | [display-e-instrumentos](../display-e-instrumentos/requirements.md) | 🟢 |
| `pt2vhf/ui/assist_panels.py` | [assistente-de-sintonia](../assistente-de-sintonia/requirements.md), [atualizacao-ota](../atualizacao-ota/requirements.md), [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md) | 🟢 |
| `pt2vhf/ui/bandkeys.py` | [display-e-instrumentos](../display-e-instrumentos/requirements.md) | 🟢 |
| `pt2vhf/ui/display_settings.py` | [display-e-instrumentos](../display-e-instrumentos/requirements.md) | 🟢 |
| `pt2vhf/ui/igate_panel.py` | [igate-aprs](../igate-aprs/requirements.md) | 🟢 |
| `pt2vhf/ui/lcd.py` | [display-e-instrumentos](../display-e-instrumentos/requirements.md), [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md) | 🟢 |
| `pt2vhf/ui/listening.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md), [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `pt2vhf/ui/live_captions_panel.py` | [legendas-e-transcricao](../legendas-e-transcricao/requirements.md) | 🟢 |
| `pt2vhf/ui/main_window.py` | [aprs-packet](../aprs-packet/requirements.md), [assistente-de-sintonia](../assistente-de-sintonia/requirements.md), [atualizacao-ota](../atualizacao-ota/requirements.md), [cat-rigctl](../cat-rigctl/requirements.md), [display-e-instrumentos](../display-e-instrumentos/requirements.md), [espectro-e-waterfall](../espectro-e-waterfall/requirements.md), [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md), [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md), [igate-aprs](../igate-aprs/requirements.md), [legendas-e-transcricao](../legendas-e-transcricao/requirements.md), [memorias-e-favoritos](../memorias-e-favoritos/requirements.md), [painel-web](../painel-web/requirements.md), [radiossonda-rs41](../radiossonda-rs41/requirements.md), [reducao-de-ruido-neural](../reducao-de-ruido-neural/requirements.md), [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md), [trafego-adsb-ais](../trafego-adsb-ais/requirements.md) | 🟢 |
| `pt2vhf/ui/occupancy_panel.py` | [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `pt2vhf/ui/panels.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md) (`MemoryDialog`, `MemoryPanel`); `ReceiverPanel`, `ModePanel`, `AudioPanel`, `DecoderPanel` servem recepcao-sdr, demodulacao-e-audio e aprs-packet sem citação explícita [Revisão] | 🟡 |
| `pt2vhf/ui/rigctl_panel.py` | [cat-rigctl](../cat-rigctl/requirements.md) | 🟢 |
| `pt2vhf/ui/satellite_panel.py` | [satelites](../satelites/requirements.md) | 🟢 |
| `pt2vhf/ui/settings_panel.py` | [atualizacao-ota](../atualizacao-ota/requirements.md), [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md), [painel-web](../painel-web/requirements.md) | 🟢 |
| `pt2vhf/ui/sonde_decoder_panel.py` | [radiossonda-rs41](../radiossonda-rs41/requirements.md) | 🟢 |
| `pt2vhf/ui/traffic_panel.py` | [trafego-adsb-ais](../trafego-adsb-ais/requirements.md) | 🟢 |
| `pt2vhf/ui/waterfall.py` | [espectro-e-waterfall](../espectro-e-waterfall/requirements.md) | 🟢 |
| `pt2vhf/updater.py` | [atualizacao-ota](../atualizacao-ota/requirements.md) | 🟢 |
| `pt2vhf/webserver.py` | [painel-web](../painel-web/requirements.md) | 🟢 |
| `run_pt2vhf.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `scripts/apply-update.ps1` | [atualizacao-ota](../atualizacao-ota/requirements.md) | 🟢 |
| `scripts/run_tests.py` | transversal (execução da suíte), ver architecture.md | 🟢 |
| `scripts/test_ota_setup_windows.ps1` | atualizacao-ota (teste Windows do instalador) | 🟡 |
| `scripts/test_ota_windows.ps1` | atualizacao-ota (teste Windows do portátil) | 🟡 |
| `scripts/verify_site.py` | atualizacao-ota (verificação da publicação no site) | 🟡 |
| `tests/__init__.py` | — (pacote Python) | n/a |
| `tests/conftest.py` | transversal (QApplication única, sem SDR real) | 🟢 |
| `tests/synth_signals.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md) | 🟢 |
| `tests/test_assist.py` | [assistente-de-sintonia](../assistente-de-sintonia/requirements.md) | 🟢 |
| `tests/test_caption_popup_ui.py` | [legendas-e-transcricao](../legendas-e-transcricao/requirements.md) | 🟢 |
| `tests/test_decoders.py` | [aprs-packet](../aprs-packet/requirements.md), [tons-dtmf-ctcss](../tons-dtmf-ctcss/requirements.md) | 🟢 |
| `tests/test_dsp.py` | [demodulacao-e-audio](../demodulacao-e-audio/requirements.md) | 🟢 |
| `tests/test_gui_smoke.py` | display-e-instrumentos, idiomas-e-configuracoes (fumaça da janela) | 🟡 |
| `tests/test_memory_engine.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md) | 🟢 |
| `tests/test_ota_no_browser.py` | [atualizacao-ota](../atualizacao-ota/requirements.md) | 🟢 |
| `tests/test_ota_site_release_redirect.py` | [atualizacao-ota](../atualizacao-ota/requirements.md) | 🟢 |
| `tests/test_rtlsdr_robust.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `tests/test_scanner_presets.py` | [memorias-e-favoritos](../memorias-e-favoritos/requirements.md), [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `tests/test_sources.py` | [recepcao-sdr](../recepcao-sdr/requirements.md) | 🟢 |
| `tests/test_v010_ui.py` | display-e-instrumentos (UI por versão, dívida D11) | 🟡 |
| `tests/test_v011_lcd.py` | [display-e-instrumentos](../display-e-instrumentos/requirements.md) | 🟢 |
| `tests/test_v012_ai_audio.py` | [legendas-e-transcricao](../legendas-e-transcricao/requirements.md), [reducao-de-ruido-neural](../reducao-de-ruido-neural/requirements.md) | 🟢 |
| `tests/test_v030_features.py` | [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md) | 🟢 |
| `tests/test_v040_tuning.py` | [gravacao-e-timeshift](../gravacao-e-timeshift/requirements.md) | 🟢 |
| `tests/test_v050_ui.py` | display-e-instrumentos (UI por versão, dívida D11) | 🟡 |
| `tests/test_v060_ui.py` | display-e-instrumentos (UI por versão, dívida D11) | 🟡 |
| `tests/test_v070_features.py` | [scanner-e-ocupacao](../scanner-e-ocupacao/requirements.md) | 🟢 |
| `tests/test_v080_integrations.py` | [cat-rigctl](../cat-rigctl/requirements.md), [memorias-e-favoritos](../memorias-e-favoritos/requirements.md), [trafego-adsb-ais](../trafego-adsb-ais/requirements.md) | 🟢 |
| `tests/test_v090_i18n.py` | [idiomas-e-configuracoes](../idiomas-e-configuracoes/requirements.md) | 🟢 |
| `tests/test_v090_sonde_sat_igate.py` | [igate-aprs](../igate-aprs/requirements.md), [radiossonda-rs41](../radiossonda-rs41/requirements.md), [satelites](../satelites/requirements.md) | 🟢 |
| `tests/test_waterfall_click_to_tune.py` | [espectro-e-waterfall](../espectro-e-waterfall/requirements.md) | 🟢 |
| `tests/test_webserver.py` | [aprs-packet](../aprs-packet/requirements.md), [painel-web](../painel-web/requirements.md) | 🟢 |

## Observações
- `pt2vhf/ui/main_window.py` aparece em 16 units: é o acoplamento central (dívida D1).
- `pt2vhf/engine.py` aparece em 9 units: orquestra DSP, decoders, gravação e distribuição.
- Units sem arquivo exclusivo de teste: cat-rigctl e trafego-adsb-ais dependem de `test_v080_integrations.py`; não há testes de `rtl_driver.py` nem de SoapySDR (dívida D10).
- Arquivos de build e CI estão descritos em `architecture.md`, `c4-containers.md` e nos ADRs, não em units funcionais.
