# Arquitetura — PT2VHF SDR Tool

Visão geral sintetizada pelo Arquiteto (Reversa, 27/11/2026) a partir do Scout, do Arqueólogo e do Detetive. Versão analisada: 0.13.3 (candidata, não publicada).

## 1. Estilo arquitetural
- 🟢 **Monólito desktop em camadas com pipeline de streaming.** Um processo Python; dados IQ fluem fonte → engine → áudio/decoders/gravação; a UI observa por eventos.
- 🟢 **Separação de threads como regra de arquitetura:** a thread Qt nunca chama o hardware nem roda DSP; a engine nunca toca em widgets. A comunicação é por filas (`engine` comandos e `engine.events`) e por um dict `status` lido no tick de 33 ms.
- 🟢 **Filas limitadas com descarte do mais antigo** em todos os pontos de pressão (fonte 32, RNNoise 8, ouvinte web 40), para que nada bloqueie a thread RF.
- 🟢 **Integrações frágeis ficam fora do processo:** RS41, ADS-B, AIS, CAT e OTA dependem de binários, arquivos ou daemons externos.
- 🟢 **Somente receptor:** nenhuma via de transmissão RF, PTT ou envio APRS-IS ligada à UI.

## 2. Diagramas
- [C4 Contexto](c4-context.md)
- [C4 Containers](c4-containers.md)
- [C4 Componentes](c4-components.md)
- [ERD completo](erd-complete.md)
- [Integrações externas](integrations.md)
- [Máquinas de estado](state-machines.md) e [ADRs](adrs/README.md)

## 3. Camadas e módulos

| Camada | Módulos | Depende de |
|---|---|---|
| Apresentação | `ui/`, `i18n.py` | engine, scanner, memory, traffic, ai_audio, integrations, dsp |
| Aplicação | `app.py`, `__main__.py`, `run_pt2vhf.py` | ui, engine, sources, dsp, integrations, ai_audio |
| Orquestração de sinal | `engine.py`, `audio.py`, `timeshift.py`, `scanner.py`, `occupancy.py` | sources, dsp, decoders, ai_audio |
| Domínio de sinal | `dsp/`, `decoders/` | NumPy/SciPy |
| Aquisição | `sources/` | pyrtlsdr, SoapySDR, socket |
| Dados locais | `config.py`, `memory.py`, `memory_regions.py`, `presets.py` | JSON |
| Integrações | `webserver.py`, `rigctl.py`, `updater.py`, `traffic.py`, `sonde_rx.py`, `satellites.py`, `aprs_map.py`, `aprs_igate.py` | rede, processos, arquivos |
| IA local | `neural_audio.py`, `live_caption.py`, `transcribe.py` | pyrnnoise, faster-whisper |

🟡 Desvio: `sources` depende de `decoders` (Arqueólogo), o que inverte a direção esperada entre aquisição e domínio.

## 4. Fluxo principal
1. A fonte entrega blocos IQ (≥ 16384 amostras) numa fila de 32.
2. A engine aplica comandos pendentes, grava timeshift, demodula o canal principal e os extras, aplica squelch, decoders (só NFM), gravação, RNNoise e envia ao áudio, à web, às legendas e ao RS41.
3. Eventos (`aprs`, `dtmf`, `activity`, `replay`, `sonde_*`, `live_caption` etc.) vão para `engine.events`.
4. A UI consome eventos e `status` a cada 33 ms e atualiza LCD, waterfall e painéis.

## 5. Build e entrega
- 🟢 Windows x64: PyInstaller (pasta + portátil) e Inno Setup por usuário; CI Windows só sob demanda (ADR 015).
- 🟢 Linux/macOS: só execução pelo código-fonte, sem binários homologados.
- 🟢 Promoção de release e verificação do site são workflows manuais separados.

## 6. Dívidas técnicas

| # | Dívida | Onde | Impacto | Confiança |
|---|---|---|---|---|
| D1 | `MainWindow` com 2371 linhas concentra sintonia, níveis, OTA, web, scanner e eventos | `ui/main_window.py` | Alto acoplamento; mudanças de UI arriscadas | 🟢 |
| D2 | Contrato de erro inconsistente em `set_center_freq` (False vs `SourceError`); `_retune` só trata False | `sources/`, `engine.py` | Exceção não tratada com rtl_tcp/Soapy fora da faixa | 🟢 |
| D3 | Limite de sintonia 24 kHz–1766 MHz fixo, inclusive para SoapySDR | `ui/main_window.py:851,1525` | Bloqueia hardware de faixa maior | 🟢 |
| D4 | `Config.save` e `MemoryBank.save` não atômicos; load de memórias sem tratar JSON corrompido | `config.py`, `memory.py` | Perda de dados em queda de energia | 🟢 |
| D5 | Código órfão: iGate e painel de feeds sem ligação; `SatellitePanel` fora das abas | `aprs_igate.py`, `ui/igate_panel.py`, `ui/traffic_panel.py`, `ui/satellite_panel.py` | Contraria o BACKLOG; superfície de manutenção | 🟢 |
| D6 | `apply_level` casa títulos de grupo em português | `ui/main_window.py:2282` | Níveis podem falhar em outros idiomas | 🟡 |
| D7 | Default de `require_key` diverge entre `WebServer` e `Config` | `webserver.py:98`, `config.py:87` | Comportamento de segurança ambíguo | 🟢 |
| D8 | Chaves de config gravadas fora de `DEFAULTS` (`rtl_library`, `vox`, `web_*`, `auto_*`, `igate_*`) | `config.py`, UI | Esquema implícito; difícil migrar | 🟢 |
| D9 | Docstring do RS41 fala em FI +12 kHz; o código usa 0 Hz | `sonde_rx.py` | Documentação enganosa | 🟢 |
| D10 | Sem testes para `rtl_driver.py` (WinUSB) e SoapySDR | `tests/` | Regressões em caminhos de instalação | 🟢 |
| D11 | Testes organizados por versão (`test_v0X0_*`) e não por módulo | `tests/` | Difícil achar a cobertura de um recurso | 🟢 |
| D12 | Dependência `sources → decoders` | `sources/` | Inversão de camada | 🟡 |
| D13 | Timeshift int8 reduz a faixa dinâmica do replay | `timeshift.py` | Qualidade do replay | 🟢 (decisão consciente, ADR 005) |
| D14 | S-meter com offset nominal de −45 dB | `dsp/demod.py` | Leituras não calibradas | 🔴 homologação |

## 7. Riscos não técnicos (homologação)
- 🔴 RS41 sem prova com RF real (P0).
- 🔴 OTA ponta a ponta no Windows (P0).
- 🔴 RNNoise e Whisper sem homologação de qualidade, CPU e latência.
- 🟡 PR #2 (classificador IQ/ONNX) experimental, fora da `main`.
