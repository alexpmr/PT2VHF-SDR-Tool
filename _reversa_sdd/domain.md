# Domínio — PT2VHF SDR Tool

Glossário e regras de negócio implícitas, extraídos pelo Detetive do código (v0.13.3, branch `claude/project-thread-hzahgn`), do CHANGELOG, do BACKLOG e do histórico git.
Escala: 🟢 confirmado no código · 🟡 inferido · 🔴 lacuna (precisa de validação humana ou RF real).

## 1. Glossário

| Termo | Significado no projeto |
|---|---|
| **SDR** | Rádio definido por software. Aqui, um receptor (RTL-SDR, rtl_tcp, SoapySDR, WAV IQ ou simulador). O produto não transmite. |
| **IQ** | Amostras complexas (fase e quadratura) entregues pela fonte em blocos. |
| **Fonte (source)** | Driver de aquisição IQ: `RtlSdrSource`, `RtlTcpSource`, `SoapySource`, `WavIQSource`, `SimulatedSource`. |
| **Centro** | Frequência em que o SDR está sintonizado. Diferente do VFO. |
| **VFO** | Frequência que o operador ouve, dentro da banda capturada em torno do centro. |
| **Offset fs/8** | Deslocamento do centro (VFO + fs/8) para tirar o sinal do pico de DC do dongle. |
| **Modo** | Demodulação: NFM, WFM, AM, USB, LSB, CW, DSB, RAW e AUTO (detecção assistida). |
| **Squelch** | Silenciador por nível em dBFS, com histerese e cauda. -150 dBFS = sempre aberto. |
| **Tone squelch** | Silenciador por subtom CTCSS. |
| **S-meter** | Medidor S1–S9+ derivado de dBFS com offset nominal (−45 dB) e calibração do usuário. |
| **Waterfall / espectro** | Visualização FFT do IQ adquirido; clique sintoniza só dentro da banda adquirida. |
| **Receptores extras** | Até 4 demoduladores adicionais no mesmo IQ. |
| **Timeshift (voltar no tempo)** | Buffer circular de IQ (int8, 20 s padrão) para reouvir o passado recente. |
| **VOX / gravação por atividade** | Gravação de áudio disparada pelo squelch, com pré-gravação e cauda. |
| **Scanner espectral** | Varredura por FFT em segmentos (idle/settle/dwell/priority/listen). |
| **Varredura de memórias** | Percorre canais salvos um a um (diferente do scanner espectral). |
| **Acerto (hit)** | Canal detectado pelo scanner acima de piso + SNR. |
| **Lockout** | Frequência excluída do scanner. |
| **Canal prioritário** | Frequência checada a cada `priority_interval_s` durante a varredura. |
| **Ocupação 24 h** | Contagem de detecções por bin de 12,5 kHz por minuto; não é medição contínua. |
| **Memória / favorito** | Canal salvo (`Memory`) em `MemoryBank`; regiões são conjuntos nomeados. |
| **Pacote de presets** | Conjunto de canais pré-definidos por categoria, importado sem duplicar. |
| **APRS / AX.25 / AFSK** | Pacotes de rádio amador em 1200 bd AFSK; decodificados nativamente só em NFM. |
| **DTMF / CTCSS** | Tons de discagem e subtons contínuos; decodificados no áudio bruto NFM. |
| **iGate** | Ponte RF→APRS-IS. Existe só como código órfão; UI removida na v0.10.0. |
| **qAO** | Construção de caminho APRS-IS obrigatória para iGate somente receptor. |
| **ADS-B / AIS** | Tráfego aéreo e marítimo, lido de decoders externos (dump1090/readsb, NMEA). Não demodulado do IQ. |
| **RS41** | Radiossonda Vaisala; decodificada a partir do mesmo IQ via `fsk_demod` + `rs41mod` externos. |
| **SGP4 / Doppler** | Propagação orbital de satélites a partir de TLE e correção de Doppler. |
| **RNNoise** | Redução de ruído neural local (pyrnnoise). |
| **Whisper** | Transcrição local (faster-whisper) com modelos tiny/base/small baixados sob ação explícita. |
| **CAT / rigctld** | Controle via Hamlib por TCP, sem PTT. |
| **Painel web** | HTTP somente leitura: página, estado, espectro e áudio PCM 16 kHz. |
| **OTA** | Atualização automática pelo site oficial com SHA-256; só nos executáveis Windows. |
| **Tipo de instalação** | `installer`, `portable` ou `source` (`updater.install_kind`). |
| **Nível de interface** | Essencial, Intermediário ou Avançado; esconde recursos, não restringe. |
| **Implementado / Testado / Homologado / Publicado** | Estados de maturidade obrigatórios do processo (ADR 018). |

## 2. Regras de negócio implícitas

### 2.1 Aquisição (sources)
- 🟢 Fila de 32 blocos; se cheia, descarta o mais antigo e incrementa `dropped` (`sources/base.py:60`).
- 🟢 Tamanho de bloco = max(16384, ⌊fs/20/16384⌋·16384) (`sources/base.py:39`).
- 🟢 A UI nunca chama a librtlsdr: comandos vão por fila para uma thread de controle (`rtlsdr_source.py:1`).
- 🟢 Sem amostras por 2 s ou comando acima de 3 s: reabre até 3 vezes; depois `failed` (`rtlsdr_source.py:451`).
- 🟢 No Windows, tenta primeiro a biblioteca RTL-SDR Blog e cai para a padrão (`rtlsdr_source.py:181`).
- 🟢 Frequência salva fora do alcance abre em 145,5 MHz (`rtlsdr_source.py:265`).
- 🟢 WinUSB só na interface 0, via `wdi-simple` com um único UAC (`rtl_driver.py:99`).
- 🟢 rtl_tcp/SoapySDR levantam `SourceError` fora da faixa, enquanto o RTL-SDR devolve False (`network_sources.py:89`). 🟡 Contrato inconsistente.

### 2.2 DSP e demodulação
- 🟢 Taxa de entrada deve ser múltiplo de 240 kHz (`dsp/receiver.py:57`).
- 🟢 De-ênfase WFM padrão 75 µs (Américas), configurável para 50 µs em `wfm_deemph_us` (`dsp/receiver.py:63`, `ui/main_window.py:820,1021`, `ui/panels.py:289`).
- 🟢 AGC só em AM/USB/LSB/CW/DSB/RAW; NFM usa ganho fixo 0,5 (`dsp/receiver.py:121`).
- 🟢 Squelch: −150 dBFS = sempre aberto; histerese 3 dB; cauda 0,25 s (`dsp/demod.py:146`).
- 🟢 S-meter: S9 = −93 dBm, 6 dB por unidade S, dBm = dBFS − 45 + calibração (`dsp/demod.py:dbfs_to_s_units`). 🔴 Offset nominal, não calibrado em RF real.
- 🟢 Decoders recebem o áudio demodulado bruto, antes de AGC, squelch e efeitos (`dsp/receiver.py:process`).
- 🟢 Detecção de modo (AUTO): WFM se largura > 60 kHz; CW se < 700 Hz ou manipulado; NFM se CV < 0,35; AM se portadora > 25% e simétrica; SSB entre 1,2 e 4,5 kHz (`dsp/assist.py:detect_mode`).
- 🟢 AUTO só aplica com confiança ≥ 0,55 e se a seleção não mudou nesse meio tempo (`ui/main_window.py:_auto_result`).

### 2.3 Engine
- 🟢 Comandos da UI são executados entre blocos, na thread DSP (`engine.py:171`).
- 🟢 Novo centro = VFO + fs/8 quando fs ≥ 900 kHz (`engine.py:219`).
- 🟢 Máximo de 4 receptores extras (`engine.py:273`).
- 🟢 AFSK/DTMF/CTCSS só rodam em NFM (`engine.py:403`).
- 🟢 Tone squelch silencia se o CTCSS medido difere mais de 1 Hz do configurado (`engine.py:407`).
- 🟢 Gravação IQ VOX: grava enquanto o squelch está aberto e até 1,5 s depois (`engine.py:341`).
- 🟢 VOX de áudio: pré-gravação 0,5 s, cauda 1,5 s, mínimo 1 s (abaixo disso apaga), máximo 300 s; troca de frequência fecha o arquivo (`audio.py:ActivityRecorder`).
- 🟢 Saída de áudio: prime de 150 ms, teto de 500 ms; underrun volta a encher (`audio.py:AudioOutput`).
- 🟢 Timeshift int8, 20 s por padrão, guarda o centro de cada trecho; replay volta ao vivo ao alcançar o presente (`timeshift.py`, `engine.py:360`).

### 2.4 Scanner e ocupação
- 🟢 A decisão de acerto é por SNR no espectro, não pelo squelch (`scanner.py:1`).
- 🟢 Segmento útil = 80% da taxa; faixa pequena põe o centro 10 kHz acima do fim (`scanner.py:start`).
- 🟢 Escuta termina com `resume_s` sem atividade ou `max_listen_s`; limiar de atividade em escuta = piso + 0,7 × SNR (`scanner.py:248-262`).
- 🟢 Cooldown de 8 s por frequência após escutar (`scanner.py:ScannerConfig`).
- 🟢 Ocupação: bins de 12,5 kHz, 1 contagem por minuto por bin, janela de 24 h (`occupancy.py`).

### 2.5 Decoders
- 🟢 AFSK: 5 fatiadores com pesos 0,5 a 2,0; o mesmo quadro em menos de 2 s é emitido uma vez (`decoders/afsk.py`).
- 🟢 AX.25: FCS CRC-16/X.25 obrigatório; quadro mínimo de 18 bytes (`decoders/ax25.py:parse_frame`).
- 🟢 APRS: símbolo terminado em `_` = estação meteorológica; `ccc/sss` vira direção/velocidade do vento (`decoders/aprs.py:parse`).
- 🟢 DTMF: tons > 60% da energia, twist ±8 dB, dois quadros iguais (`decoders/tones.py:_frame`).
- 🟢 CTCSS: pico > 15 dB sobre a mediana e > 2% da energia, janela de 1 s (`decoders/tones.py:CTCSSDetector`).

### 2.6 Memórias e configuração
- 🟢 Pacotes de presets não duplicam: chave = categoria + freq/100 (`presets.py:import_packs`).
- 🟢 Nome de região: 1 a 100 caracteres, sem caracteres de controle (`memory_regions.py:_check`).
- 🟢 Importação CHIRP: FM→NFM 12 kHz, NFM→8 kHz, WFM→180 kHz, AM→8 kHz, SSB→2,7 kHz, CW→500 Hz (`memory.py:import_csv`).
- 🟢 Config inválida volta aos padrões sem aviso; `save` não é atômico (`config.py`). 🟡 Risco de perda de configuração em queda de energia.
- 🟢 Configuração fica em `%APPDATA%\PT2VHF-SDR-Tool` ou `~/.config/PT2VHF-SDR-Tool`.

### 2.7 Tráfego, sondas e satélites
- 🟢 ADS-B, AIS e sondas externas não são demodulados do IQ; só arquivos externos (`traffic.py:1`).
- 🟢 AIS lê só os últimos 2 MB; JSON acima de 8 MB é recusado (`traffic.py:load_traffic`).
- 🟢 RS41 só entre 400 e 406 MHz, IQ ≥ 96 kS/s, binários sem download automático (`sonde_rx.py`).
- 🔴 RS41 nunca validado com RF real (P0).

### 2.8 IA de áudio
- 🟢 RNNoise só em NFM/AM/USB/LSB/DSB; fila de 8 descarta o mais antigo (`neural_audio.py`).
- 🟢 Falha do RNNoise nunca silencia o áudio (`neural_audio.py:_run`).
- 🟢 Modelos Whisper só baixam por ação explícita; inferência com `local_files_only` (`live_caption.py`).
- 🟢 Legenda a cada ≥ 4 s; ignora trechos com pico < 0,009 (`live_caption.py:feed`).
- 🔴 Qualidade, CPU e latência com RF real não homologadas.

### 2.9 Integrações
- 🟢 Web: só GET; ver `permissions.md`. Áudio PCM 16 kHz, fila de 40 blocos por ouvinte (`webserver.py:AudioHub`).
- 🟢 CAT: comandos `f`, `m`, `F`, `M`; sem PTT (`rigctl.py`).
- 🟢 OTA: manifesto sem redirect; pacote em www.pt2vhf.com; redirect só para a release GitHub da versão; tamanho e SHA-256 obrigatórios (`updater.py`).
- 🟢 OTA adiada durante gravação, scanner, varredura de memórias e replay (`ui/main_window.py:1441`).
- 🔴 OTA em campo registrada como falhando (CLAUDE.md, BACKLOG P0).

### 2.10 Interface e aplicação
- 🟢 Sintonia limitada a 24 kHz–1766 MHz, inclusive para SoapySDR (`ui/main_window.py:851,1525`). 🟡 Limite do RTL aplicado a outras fontes.
- 🟢 Clique no waterfall só dentro do IQ adquirido, arredondado ao passo (`ui/waterfall.py:_pick_frequency`).
- 🟢 Widgets só na thread principal; eventos da engine chegam pelo tick de 33 ms (`ui/main_window.py:_tick`).
- 🟢 Bandas incompatíveis com a fonte ficam ocultas (v0.13.0).
- 🟢 Mutex `PT2VHF_SDR_Tool_Running` impede duas instâncias no Windows (`app.py`).
- 🟢 Autoteste não usa RF real nem valida RS41/ADS-B/AIS/OTA ponta a ponta (`app.py:selftest`).

## 3. Regras de processo (não estão no código)
- 🟢 Implementado ≠ testado ≠ homologado ≠ publicado (CLAUDE.md, ADR 018).
- 🟢 Testes sintéticos não substituem RF real.
- 🟢 O produto é prioritariamente receptor: sem transmissão RF, PTT, iGate ou portas abertas por suposição.
- 🟢 Não enviar áudio de recepção a APIs externas nem criar telemetria sem consentimento.

## 4. Lacunas para validação humana
- 🔴 RS41 com RF real (serial, frame, posição e altitude no mapa).
- 🔴 OTA ponta a ponta no Windows (instalador e portátil).
- 🔴 Calibração do S-meter.
- 🔴 Qualidade de RNNoise e Whisper com sinais reais.
- 🟡 Se o código órfão do iGate (`aprs_igate.py`, `ui/igate_panel.py`) deve ser removido, como pede o BACKLOG.
- 🟡 Se o limite 24 kHz–1766 MHz deveria depender da fonte.
- 🟡 Se `web_require_key` deveria ter o mesmo default em `Config` e em `WebServer`.
