# Análise de código — PT2VHF-SDR-Tool

> Gerado pelo **Arqueólogo** (Reversa) em 2026-11-27, branch do PR #32 (base `c118eff`, v0.13.3). Nível: **completo**.
> Escala: 🟢 CONFIRMADO (lido no código) · 🟡 INFERIDO · 🔴 LACUNA
> Fluxogramas em `flowcharts/<modulo>.md`; entidades em `data-dictionary.md`; dados estruturados em `.reversa/context/modules.json`.

---

## Módulo `sources` — aquisição de IQ

Arquivos: `pt2vhf/sources/base.py`, `rtlsdr_source.py`, `rtl_driver.py`, `network_sources.py`, `sim_sources.py`.

### Contrato comum (`IQSource`) 🟢
- Toda fonte entrega blocos `complex64` por `read(timeout=0.5)`; a produção ocorre numa thread própria (`src-<nome>`) que alimenta uma `queue.Queue(maxsize=32)`.
- **Política de fila cheia:** `_push` descarta o bloco **mais antigo**, incrementa `dropped` e enfileira o novo (prioriza latência sobre completude) — `base.py:60-68`.
- **Tamanho do bloco:** `_choose_block(fs) = max(16384, floor(fs/20 / 16384) * 16384)` → ~20 blocos/s, múltiplo de 16384 (exigência do librtlsdr: múltiplo de 512 bytes) — `base.py:39-43`.
- Capacidades declaradas por flags de classe: `tunable`, `supports_gain`, `supports_ppm`, `supports_bias_tee`, `supports_direct_sampling`, `gains_db`.
- `check_freq(hz) -> str`: string vazia = alcançável; senão mensagem para o usuário.
- Conversão de bytes u8 do RTL: `(u8 - 127.4) / 128` → I/Q intercalados — `base.py:99-103`.

### `RtlSdrSource` (USB) 🟢
Princípio de projeto declarado (v0.4.0): **a interface nunca chama a librtlsdr diretamente**.
- **Três threads:** `rtl-read` (leitura assíncrona `read_samples_async`), `rtl-ctl` (fila de comandos `_ctl` aplicados ao dongle) e `rtl-watch` (vigia a cada 250 ms).
- **Vigia/recuperação:** fluxo parado se não chegar bloco por `STALL_S = 2.0 s`, ou se um comando ficar ocupado por mais de `CMD_TIMEOUT_S = 3.0 s`. Até `MAX_RECOVER = 3` tentativas de reabrir o dispositivo, reaplicando frequência/ganho/PPM/bias-T; depois `status = "failed"` e a fonte para — `rtlsdr_source.py:451-479`.
- `status` ∈ {`ok`, `recovering`, `failed`}; mensagens ao usuário vão para `_messages` e o motor as coleta por `pop_messages()` (`engine.py:439`).
- **Seleção de biblioteca:** preferência global `_PREF["lib"]` ∈ {`auto`, `blog`, `standard`}. No Windows com a DLL do driver RTL-SDR Blog embarcada (`rtlsdr_blog/rtlsdr.dll`) tenta `blog` e, em falha (ex.: `LIBUSB_ERROR_ACCESS`), cai para `standard`, avisando o usuário. Fora do Windows sempre `standard`.
- `_DllWithStubs`: funções `rtlsdr_*` ausentes na DLL viram stubs que retornam 0, porque o pyrtlsdr 0.5 chama `rtlsdr_set_dithering` logo após abrir (bug corrigido na 0.4.1).
- `_construct`: se o construtor falhar depois de abrir o handle USB, fecha-o antes de tentar a próxima biblioteca (WinUSB é exclusivo).
- **Frequência salva fora do alcance** na abertura → abre em 145,5 MHz e avisa.
- **Fechamento nunca bloqueia a UI:** `stop()`/`close()` delegam `cancel_read_async`/`close` a threads em segundo plano; a próxima abertura espera fechamentos pendentes (`_CLOSING`, até 3 s cada).
- Erros de comando: frequência recusada restaura a anterior e avisa; outros ajustes só logam.

**Faixa sintonizável** (`tuning_range`) 🟢:

| Condição | Faixa |
|----------|-------|
| amostragem direta ligada | 0,5–28,8 MHz |
| E4000 | 52–2200 MHz |
| FC0012/FC0013 | 22–1100 MHz |
| FC2580 | 146–924 MHz |
| R828D + biblioteca Blog + produto contém "V4"/"BLOG" | 0,5–1766 MHz (HF pelo upconverter interno) |
| demais (R820T/R828D) | 24–1766 MHz |

Abaixo de 24 MHz a mensagem de erro sugere V4, amostragem direta (ramo Q) no V3 ou upconverter.

### `rtl_driver` (preparação WinUSB no Windows) 🟢
- Detecta interfaces `VID_0BDA&PID_2838/2832` via PowerShell `Get-PnpDevice … | ConvertTo-Json`.
- Interface pronta se o serviço ∈ {`winusb`, `libusbk`, `libusb0`, `libusb0_x64`}. Só a interface de rádio (MI 0 ou não composta) é considerada.
- Instalação: `wdi-simple.exe` embarcado, elevado por `ShellExecuteExW("runas")` (um UAC), **somente WinUSB (`-t 0`) e somente interface 0 (`-i 0`)**, timeout de espera 180 s.
- `diagnose()` monta relatório texto: biblioteca, dispositivos, PnP, instalador embarcado, teste de abertura do #0.

### `RtlTcpSource` 🟢
- Handshake: 12 bytes com magic `RTL0`, tipo de sintonizador e nº de ganhos.
- Comandos `>BI`: `0x01` freq, `0x02` sample rate, `0x03` modo de ganho, `0x04` ganho (décimos de dB), `0x05` PPM, `0x08` AGC do RTL, `0x09` amostragem direta, `0x0E` bias-T.
- Tabela fixa de 29 ganhos (R820T).
- **Divergência de contrato:** `set_center_freq` fora da faixa **lança `SourceError`**, enquanto `RtlSdrSource` retorna `False` e avisa 🟢. `check_freq` não considera o produto, então o HF do V4 via rtl_tcp é recusado 🟡.

### `SoapySource` 🟢
- Importação tardia de `SoapySDR`; ganhos em passos de 1 dB pelo `getGainRange`; faixas por `getFrequencyRange`. Falta de faixas → toda frequência recusada.
- Lê em `CF32` com `timeoutUs=500000`.

### `SimulatorSource` 🟢
Banda sintética determinística (`default_rng(1234)`), ruído `noise_db = -60`, ganho fictício 30 dB:

| Frequência | Modo | Conteúdo |
|-----------|------|----------|
| 145,570 MHz | NFM | 5 quadros APRS AFSK1200 alternados a cada 6 s (posição, Mic-E, clima, telemetria, mensagem) |
| 145,430 MHz | NFM | melodia 7 s/10 s + CTCSS 88,5 Hz + DTMF `1479#` entre 4 e 6,5 s |
| 145,800 MHz | CW | "CQ CQ DE PT2VHF PT2VHF K", 18 WPM |
| 145,650 MHz | AM | tom 1 kHz, 70 % |
| 145,250 MHz | USB | dois tons 700 + 1900 Hz |
| 98,100 MHz | WFM | acorde, desvio 50 kHz |

### `WavIQSource` 🟢
- WAV estéreo I=esq, Q=dir; 8/16/32 bits. Não sintonizável. Frequência central extraída do nome (`(\d{6,11})\s*Hz`) ou 100 MHz. Repete em loop por padrão; ritmo em tempo real.

---

## Módulo `dsp` — cadeia de recepção

Arquivos: `pt2vhf/dsp/filters.py`, `demod.py`, `receiver.py`, `audiofx.py`, `assist.py`.

### Blocos com estado (`filters.py`) 🟢
Todos preservam estado entre blocos, de modo que processar em pedaços = processar o sinal inteiro.
- `NCO`: mixer com fase contínua; desloca por `-freq`.
- `FIRFilter`: overlap-save; usa `np.convolve` quando o buffer < 4×taps, senão `scipy.signal.oaconvolve`.
- `Decimator(factor, cutoff, numtaps=8·factor+1)`: `firwin(cutoff/factor)` + decimação com fase preservada.
- `SOSFilter`, `IIRFilter`, `DCBlocker(r=0.995)`.
- `bandpass_complex_taps`: passa-faixa complexo (Kaiser β=7) que permite bandas assimétricas (USB/LSB).
- `deemphasis(fs, tau)`: 1ª ordem por transformação bilinear com pré-distorção.

### Taxas e modos (`receiver.py`) 🟢
- `IF_RATE = 240 000`, `AUDIO_RATE = 48 000`. A taxa de entrada **precisa** ser múltiplo de 240 kHz (`ValueError` caso contrário).
- `SAMPLE_RATES = [240k, 960k, 1.2M, 1.44M, 1.92M, 2.4M, 2.88M]`.

| Modo | Passa-faixa padrão (Hz) | Passo | Larguras pré-definidas |
|------|-------------------------|------:|------------------------|
| NFM | −6000…6000 | 12 500 | 6k, 8k, 11k, 12,5k, 16k |
| WFM | −90 000…90 000 | 100 000 | 120k, 150k, 180k |
| AM | −4500…4500 | 5000 | 3k, 6k, 9k, 12k |
| USB | 300…2800 | 100 | 1,8k, 2,4k, 2,7k, 3k |
| LSB | −2800…−300 | 100 | idem |
| CW | −250…250 | 10 | 100, 250, 500, 1000 |
| DSB | −3000…3000 | 100 | 4k, 6k |
| RAW | −12 000…12 000 | 1000 | 24k |

`passband_for`: USB → `[300, 300+w]`; LSB → `[−300−w, −300]`; demais simétricos.

### Pipeline `Receiver.process(iq)` 🟢
1. NCO desloca o VFO para 0 Hz (`offset_hz = VFO − centro`).
2. `stage1`: decima para 240 kHz (`numtaps = 12·fator + 1`, cutoff 0,85). Se `keep_if`, guarda `last_if` (usado pelo assistente).
3. Noise blanker (opcional).
4. **WFM:** filtro de canal a 240 kHz (129 taps) → FM (desvio 75 kHz) → de-ênfase (`tau` padrão **75 µs**, Américas) → passa-baixa Butterworth 8ª ordem 15 kHz → decima para 48 kHz.
   **Demais:** decima 240→48 kHz (61 taps) → canal (257 taps) → demodulador → (NFM: de-ênfase 750 µs se `nfm_deemph`) → AGC nos modos AM/USB/LSB/CW/DSB/RAW; NFM recebe ganho fixo 0,5.
5. `signal_db = power_db(canal)` (potência média do canal, dBFS).
6. Squelch por nível → filtros de tom → notch → redução de ruído → equalizador.
7. `rec_audio_raw = soft_limiter(a)` (sempre, para pré-gravação VOX); `rec_audio` = raw se squelch aberto, senão zeros.
8. Saída: zeros se squelch fechado ou mudo; senão `soft_limiter(a · volume · 2)`.
9. Retorna `(áudio_saída, áudio_bruto_para_decoders)`; o áudio dos decoders é tirado **antes** de AGC/squelch/efeitos.

- NFM: desvio do discriminador = 5 kHz se largura > 9 kHz, senão 2,5 kHz.
- CW: BFO = `cw_pitch` (700 Hz).
- `compute_spectrum(iq, nfft, max_frames=8, window="blackmanharris")`: média de até 8 FFTs, normalizada por `sum(w)²`, em dBFS com `fftshift`; janelas em cache.

### Demodulação e controle de nível (`demod.py`) 🟢
- `FMDemod`: discriminador por `angle(x·conj(x[n−1]))`, ganho `fs / (2π·desvio)`.
- `AMDemod`: envoltória + DC blocker (0,999).
- `SSBDemod`: parte real após somar BFO opcional.
- `AGC`: sub-blocos de 5 ms; ataque instantâneo; hang e decaimento por preset — Rápido (0,05 s/0,05 s), Médio (0,3/0,2), Lento (1,0/0,5); alvo 0,3; ganho máx. 80 dB; ganho interpolado por amostra. Desligado → ganho manual em dB.
- `NoiseBlanker`: zera amostras com |x| > 6 × média móvel da mediana (α 0,2), alargando ±2 amostras.
- `Squelch`: limiar em dBFS, **−150 = sempre aberto** (≤ −149), histerese 3 dB, cauda 0,25 s.
- `dbfs_to_s_units`: `dBm = dBFS − 45 + calibração`; S9 = −93 dBm (IARU VHF/UHF), 6 dB por unidade S; acima de S9 mostra `S9+N`. O offset −45 é nominal para RTL-SDR com ganho médio 🟢 (precisão real 🔴 sem calibração).

### Efeitos de áudio (`audiofx.py`) 🟢
- Equalizador de 8 bandas (100, 200, 400, 800, 1600, 3200, 6400, 12 000 Hz), biquads *peaking* RBJ Q=1,1; bandas com |ganho| ≤ 0,05 dB são omitidas. Presets: Plano, Voz (SSB/FM), Voz clara, Graves, Música (WFM), Telefonia.
- Notch manual IIR (Q=15, padrão 1 kHz).
- `ToneFilters`: passa-altas Butterworth 6ª ordem 300 Hz (remove CTCSS) e passa-baixas opcional.
- `NoiseReduction`: subtração espectral STFT (quadro 512, hop 256, janela √Hann), piso por mínimo seguido (desce 0,7/0,3, sobe ×1,002), ganho limitado a [0,08; 1], suavização temporal 0,6/0,4, sobre-subtração 1,5. Latência de 1 quadro.
- `soft_limiter`: `tanh(x/0.9)·0.9`.

### Assistente de sintonia (`assist.py`) 🟢
- `estimate_ssb_offset`: reamostra para 8 kHz, STFT (512/256, nfft 4096), branqueia picos vs. mediana local (~150 Hz), seleciona quadros sonoros, e varre Δ ∈ [−600, 600] Hz (passo 5) × f0 ∈ [75, 330) Hz comparando energia em `Δ + k·f0` vs. inter-harmônicos. Desempata *aliases* com a borda inferior da voz (~300 Hz) como prior gaussiano σ=90 Hz; refina ±6 Hz em passos de 1 Hz. Rejeita se harmonicidade < 6 dB ou < 8 quadros sonoros. Confiança = destaque do pico sobre o 2º melhor (fora de ±40 Hz).
- `occupied_band`: PSD de Welch, suavização ~150 Hz, limiar `max(piso_p5 + thresh, máx − 35 dB)`, cresce a partir do bin mais próximo de 0 Hz tolerando lacunas de 1200 Hz; ignora se o sinal mais próximo estiver a > 15 kHz.
- `detect_mode` (árvore de decisão) — ver `flowcharts/dsp.md`: WFM (> 60 kHz), CW (estreito/manipulado), NFM (envoltória constante, CV < 0,35, 3–30 kHz), AM (portadora > 25 % e simétrica), USB/LSB (1,2–4,5 kHz sem portadora, lado pelos harmônicos; fallback pela convenção da faixa: ≥ 10 MHz USB), NFM provável, AM genérico.
- `adaptive_passband`: margens 150 Hz (SSB/CW) ou 600 Hz; limites mínimos AM 2,5 kHz, NFM 4 kHz, WFM 50 kHz; máximos 15 kHz (100 kHz WFM).
- `fine_tune`: SSB pela voz; AM/CW pelo pico com interpolação parabólica; NFM/WFM/DSB pelo centro; encaixa no canal do passo (≥ 2,5 kHz) se a diferença ≤ 30 % do passo.

---

## Módulo `decoders` — APRS, DTMF, CTCSS

Arquivos: `pt2vhf/decoders/afsk.py`, `ax25.py`, `aprs.py`, `tones.py`.

### AFSK 1200 (Bell 202) 🟢
- Mark 1200 Hz, space 2200 Hz, 1200 baud. Entrada: áudio FM bruto a 48 kHz, decimado para **9600 Hz** (8 amostras/bit).
- Passa-faixa Butterworth 4ª ordem 900–2500 Hz, normalização por RMS do bloco, correlação não coerente com kernels mark/space de 1 bit.
- **5 fatiadores em paralelo** com pesos de space {0,5; 0,7; 1,0; 1,4; 2,0} para compensar ênfase do transmissor (técnica inspirada no Dire Wolf).
- `_Slicer`: DPLL que puxa a fase 30 % em direção a 0,5 a cada transição; NRZI (sem transição = 1).
- **Dedupe:** o mesmo quadro (texto TNC2) recebido de vários fatiadores em < 2 s é emitido uma vez; o dicionário é podado acima de 64 entradas (mantém < 5 s).
- `afsk_modulate`: gerador usado pelo simulador e testes (30 flags de preâmbulo, 3 de cauda).

### AX.25/HDLC 🟢
- FCS CRC-16/X.25 (poly refletido 0x8408, init/xor 0xFFFF), LSB primeiro.
- Endereços: 6 caracteres deslocados 1 bit + byte SSID (`0x60 | ssid<<1 | H | último`); `*` marca *has-been-repeated*.
- `parse_frame`: mínimo 18 bytes, FCS obrigatório, até 10 endereços.
- `HDLCDeframer`: flag 0x7E; abort com > 6 uns; remove bit de stuffing após 5 uns; descarta quadros > 400 bytes ou com bits não múltiplos de 8; exige ≥ 143 bits entre flags.

### Parser APRS 🟢
Tipos produzidos (`APRSPacket.type`): `Posição`, `Clima`, `Mic-E`, `Status`, `Mensagem`, `Telemetria (def.)`, `Telemetria`, `Objeto`, `Terceiros`, `Outro`.
- Posição não comprimida (`DDMM.mmN/DDDMM.mmE` com ambiguidade por espaços) e comprimida (base 91; curso/velocidade ou altitude conforme byte de tipo).
- `ccc/sss` após a posição = curso/velocidade (nós → km/h ×1,852); `/A=nnnnnn` = altitude em pés (×0,3048).
- Símbolo terminando em `_` = estação meteorológica; nesse caso `ccc/sss` vira direção/velocidade do vento.
- Mic-E: latitude e hemisférios no campo destino; longitude, velocidade, curso e símbolo nos bytes de info; altitude `xxx}` em base 91 − 10000 m.
- Mensagens: destinatário 9 caracteres, remove `{id`; prefixos `PARM./UNIT./EQNS./BITS.` → definição de telemetria.
- Telemetria `T#seq,A1..A5,bits`.
- Erros de índice/valor não derrubam: o texto vai para `comment`.
- Utilidades: `distance_bearing` (haversine, R = 6371 km), `maidenhead` (4/6 caracteres), `locator_to_latlon` (centro do quadrado).

### DTMF e CTCSS 🟢
- `goertzel_power`: implementado como produto matricial com exponenciais complexas, com cache de até 16 kernels.
- **DTMF:** 8 kHz, quadros de 205 amostras (~25,6 ms). Aceita tecla se: energia dos dois tons > 60 % do total; 2º maior de cada grupo < 15 % do maior; *twist* dentro de ±8 dB; **mesma tecla em 2 quadros seguidos**; emite uma vez por pressionamento.
- **CTCSS:** decima 48k→6k→1k Hz, janela de 1 s com Hann, 51 tons de 67,0 a 254,1 Hz. Detecta se o pico supera a mediana dos demais (excluindo vizinhos) em > 15 dB e tem > 2 % da energia.

---

## Módulo `engine` — motor, áudio, gravação e "voltar no tempo"

Arquivos: `pt2vhf/engine.py`, `audio.py`, `timeshift.py`.

### Modelo de concorrência 🟢
- Uma thread `dsp` (`Engine._loop`) lê a fonte, processa e publica. A UI **nunca** mexe no `Receiver` diretamente: usa `Engine.call(fn)`, que enfileira `fn(rx)` em `_cmds` para execução **entre blocos** (ou na hora, se o motor estiver parado).
- Saídas para a UI são **lidas por polling**: `events` (fila de tuplas `(tipo, dado, timestamp)`), `status` (dict), `spectrum`, `wf_lines` (deque de 200 linhas).
- Gravadores de áudio/IQ são protegidos por `_lock`.
- Mensagens da fonte (`pop_messages`) viram eventos `source_msg`; fonte parada (`source._running == False` e sem bloco) gera `error` "A fonte de sinal parou." e encerra o loop.
- `status["cpu"]` = média móvel (0,9/0,1) de tempo de processamento ÷ duração do bloco; `status["dropped"]` = blocos descartados pela fonte.

### Tipos de evento publicados 🟢
`aprs` (APRSPacket), `dtmf` (dígito), `neural_error`, `replay` (segundos atrás), `replay_end`, `source_msg`, `error`, `activity` e `vox` (dict da transmissão gravada).

### Sintonia e centro 🟢
- `tune(freq)`: grava `vfo` e chama `_retune`.
- `_retune`: margem útil = `fs/2·0,9 − largura/2`. Se o VFO sair da margem (ou `force`), novo centro = **VFO + fs/8** quando fs ≥ 900 kHz (afasta o pico DC do RTL-SDR do canal), senão o próprio VFO. Se a fonte recusar (`False`), mantém o centro e limita o offset a ±0,95·fs/2. Mudança de centro limpa o waterfall.
- Fonte não sintonizável (WAV IQ) ou `hold_center=True` (scanner): só desloca o canal, offset limitado a ±0,95·fs/2.
- `set_center(freq)` (scanner): muda o centro, esvazia a fila da fonte, limpa waterfall e força a próxima linha de espectro.

### `process_block(blk)` 🟢
Ordem fixa: comandos pendentes → remoção de DC (`blk − mean`) → gravação IQ (se `iq_vox`, só com squelch aberto ou até 1,5 s depois) → ouvintes de IQ (`iq_listeners`, usados pelo RS41) → espectro na cadência `wf_speed` (padrão 20 linhas/s, `compute_spectrum` com 6 quadros) → buffer de timeshift → (se em replay, lê do buffer e ajusta offset pelo centro gravado) → `Receiver.process` → captura de FI para o assistente → mistura de receptores extras (soma + `tanh`) → CTCSS (só NFM) → **tone squelch** (silencia se o CTCSS medido diferir > 1 Hz do exigido) → AFSK e DTMF (só NFM) → status → áudio neural (ou publicação direta) → gravadores VOX/atividade.

### Receptores extras 🟢
- Até **4** (`add_extra` retorna `None` acima disso ou sem fonte). Cada um é um `Receiver` completo na mesma faixa; fora de `±0,9·fs/2` do centro fica `in_span = False` e é ignorado. Na troca de fonte são recriados preservando modo, passa-faixa, volume e squelch.
- Extras processam sempre o IQ **ao vivo**, mesmo durante replay 🟢.

### Publicação de áudio (`_publish_audio`) 🟢
Saída da placa → `audio_listeners` (stream LAN, legendas) → gravação de áudio manual. Se `NeuralAudioWorker.feed()` aceitar o bloco, a publicação passa a ser feita pelo worker (RNNoise) fora da thread DSP.

### Gravação 🟢
- Áudio manual: `PT2VHF_AAAAMMDD_HHMMSS_<vfo>Hz_AF.wav`, 48 kHz mono 16 bits.
- IQ: `PT2VHF_AAAAMMDD_HHMMSS_<centro>Hz_IQ.wav`, estéreo 16 bits na taxa da fonte (compatível com `WavIQSource`).
- `ActivityRecorder` (scanner e VOX): pré-gravação 0,5 s, cauda 1,5 s, mínimo 1 s (arquivos menores são apagados), máximo 300 s (divide), troca de frequência > 1 Hz fecha a transmissão. Modo por transmissão: `<pasta>/<AAAA-MM-DD>/HHMMSS_<f>MHz_<modo>.wav` (sufixo `_2`, `_3` em colisões). Modo `single_file`: um WAV `_VOX` por sessão só com as transmissões. Usa `rec_audio_raw` (antes do squelch e do volume). "Aberto" exige squelch ativo (limiar > −149 ou tone squelch), squelch aberto e tom correto.

### `AudioOutput` 🟢
- PortAudio mono float32, bloco 1024, latência "low". Buffer alvo **150 ms** antes de tocar (*priming*); teto 500 ms (descarta o mais antigo). Underrun preenche com zeros, conta `underruns` e volta a acumular — compensa a diferença de clock SDR × placa.
- Sem dispositivo: `available = False`, `error` preenchido; o restante segue sem áudio.

### `TimeShiftBuffer` 🟢
- Buffer circular de IQ **int8** (escala 127), capacidade `fs × segundos` (padrão 20 s → 1,2 MHz × 20 s × 2 B = 48 MB).
- Guarda a frequência central por trecho (`_centers`), permitindo reouvir qualquer frequência da faixa gravada em qualquer modo.
- `start_replay(s)` posiciona `max(written − s·fs, oldest)`; ao alcançar o ao vivo emite `replay_end`. Quantização para 8 bits iguala a resolução do RTL-SDR, mas perde faixa dinâmica de fontes melhores (SoapySDR) 🟡.

---

## Módulo `scanner` — varredura por espectro e ocupação

Arquivos: `pt2vhf/scanner.py`, `occupancy.py`.

### Princípio 🟢
O scanner **não usa o squelch de áudio**: decide pela SNR no espectro, permitindo milhares de canais/s (segmentos de 80 % da taxa, ~1,9 MHz a 2,4 MS/s).

### `detect_signals` 🟢
- Usa só 85 % central da faixa, ignora ±3 kHz em torno do centro (pico DC) e exige ≥ 8 bins válidos.
- Piso = mediana dos bins válidos; sinal = bins acima de piso + `snr_db`. Agrupa bins com lacuna ≤ 2; frequência = **centróide de potência** arredondado à `resolution`. Ordena por SNR decrescente.

### Segmentação 🟢
- Faixa ≤ 80 % da taxa: um segmento; se couber (faixa + 10 kHz ≤ 40 % da taxa) o centro fica 10 kHz **acima** do fim, deixando o pico DC fora; senão no meio.
- Faixa maior: `ceil(faixa / útil)` segmentos centrados em `f0 + útil/2 + k·útil`.

### Máquina de estados (`SpectrumScanner`) 🟢
Estados: `idle`, `settle`, `dwell`, `priority`, `listen` — ver `flowcharts/scanner.md`.
- `settle`: descarta `settle_lines` (2) linhas após mudar o centro; linhas com centro diferente do alvo são ignoradas.
- `dwell`: *max-hold* de `dwell_lines` (4) linhas, então `detect_signals`. Novo hit se não houver um existente a ≤ `max(1,5·resolução, largura/3)`.
- **Canal prioritário:** a cada `priority_interval_s` (3 s) verifica a frequência prioritária (no mesmo segmento ou indo a `p + fs/8`); se acima de piso + SNR, passa a escutar.
- `listen` (só se `cfg.listen`): escolhe a 1ª detecção não bloqueada e fora de *cooldown* (8 s por frequência); retoma quando o nível cai abaixo de piso + 0,7·SNR por `resume_s` (2 s) ou estoura `max_listen_s` (0 = sem limite).
- **Lockout:** frequências bloqueadas com tolerância `max(resolução, largura/2)`; bloquear remove o hit.
- `channels_per_second = (fs·0,8 / resolução) ÷ ((dwell + settle) / linhas_por_s)`.
- Eventos para a UI: `hit` (Hit, novo?), `listen`, `priority`, `resume`, `segment`.

**Faixas pré-definidas** (`SCAN_PRESETS`, 15 itens) 🟢: aviação 118–137 AM; marítimo 156–162,05; 2 m; 70 cm; VHF serviços 148–174; UHF 450–470; FRS 462,5–467,75 (2,5 kHz); PMR446; PX 11 m (requer HF); radiossondas 400–406; FM broadcast 76–108 (WFM, SNR 15); ondas curtas 49/31/25/19 m (requer HF).

### `OccupancyHistory` 🟢
- Janela móvel de **24 h** por hora cheia; frequências em *bins* de **12,5 kHz**; aceita 24 kHz–2 GHz (senão `ValueError`).
- No máximo **uma contagem por minuto por bin** (`_seen`).
- `matrix(limit=80)`: 24 colunas horárias e as 80 frequências mais ativas.
- Persistência JSON `{schema: 1, bin_hz, hours}` com escrita atômica (`.tmp` + `replace`), no máximo a cada 20 s salvo `force`.
- Fonte dos dados: detecções do scanner, não medição contínua 🟢.

---

## Módulo `memory` — memórias, presets e configuração

Arquivos: `pt2vhf/memory.py`, `memory_regions.py`, `presets.py`, `config.py`.

### Plano de bandas (`BAND_PLAN`) 🟢
21 faixas (IARU R2/Anatel, referência rápida) com modo e passo padrão, de 160 m (LSB) a 23 cm (NFM), incluindo PX 11 m (AM, 10 kHz), FM broadcast (WFM, 100 kHz), aviação (AM, **8,333 kHz**), satélites meteorológicos 137–138 MHz, marítimo (NFM, 25 kHz), PMR/uso livre. `band_for(freq)` devolve a primeira faixa que contém a frequência.

### `MemoryBank` 🟢
- JSON `{categories, channels[]}`; sem arquivo → carrega `default_memories()` (10 exemplos reais + 4 do simulador).
- 9 categorias padrão: Repetidoras, Simplex, APRS / Digital, Satélites, Aviação, Marítimo, Broadcast, Utilidades, Favoritos. Adicionar canal com categoria nova cria a categoria.
- `load()` ignora campos desconhecidos (compatibilidade para frente) mas **não trata JSON corrompido** (exceção sobe) 🟢; `save()` não é atômico 🟢.
- **CSV CHIRP:** exporta com as 14 colunas do CHIRP + `Category`; NFM com largura < 9 kHz vira `NFM`, senão `FM`; `Duplex` pelo sinal do offset; nome truncado em 16 caracteres; DTCS fixo `023/NN`; TStep `5.00`.
  Importa: `FM`→NFM 12 kHz, `NFM`→8 kHz, `WFM`→180 kHz, `AM`→8 kHz, `USB/LSB`→2,7 kHz, `CW`→500 Hz, outros → NFM; tom só se `Tone`/`TSQL`; categoria = parâmetro, coluna `Category` ou Repetidoras (com offset)/Simplex.

### `RegionMemoryStore` 🟢
- Perfis por região num único JSON `{regions: {nome: {categories, channels}}}`, escrita atômica.
- Nome válido: 1–100 caracteres sem controle. Importar CHIRP sem canais válidos → `ValueError`.
- `load_bank` **substitui** o banco ativo inteiro e salva.

### Pacotes de memórias prontas (`presets.py`) 🟢
8 pacotes: `ham` (chamada FM/SSB e fonia HF), `digital` (FT8/FT4/WSPR), `sat` (ISS, SO-50), `air` (121,5; 123,45; 243; ACARS 131,55), `marine` (17 simplex + DSC 70 + AIS 1/2), `px` (40 canais, com 23/24/25 invertidos), `frs` (22 FRS + 16 PMR446), `time` (WWV/CHU).
`import_packs` não duplica: chave `(categoria, round(freq/100))`, isto é, mesma categoria e mesma frequência com resolução de 100 Hz; cada canal importado ganha novo `id`.

### `Config` 🟢
- `dict` com 70+ chaves padrão (`DEFAULTS`), mesclado com `config.json` do diretório do usuário (`%APPDATA%` no Windows, `XDG_CONFIG_HOME` ou `~/.config` nos demais). JSON inválido é ignorado silenciosamente (volta aos padrões).
- `first_run = not path.exists()`.
- `save()` engole `OSError` e **não é atômico** 🟢.
- Padrões relevantes: fonte RTL-SDR, 1,2 MS/s, VFO 145,570 MHz, NFM 12 kHz, passo 12,5 kHz, ganho 30 dB, squelch −150 (aberto), de-ênfase WFM 75 µs, FFT 4096, waterfall −110…−40 dB "Kiwi" a 20 linhas/s, LCD "Âmbar", timeshift 20 s, `check_updates = True`, `reconnect_on_start = True`, `web_require_key = False`, `my_locator = "GG66qk"`, `my_callsign = "PT2VHF"`, gravações em `~/PT2VHF-Gravacoes`.

---

## Módulo `traffic` — ADS-B, AIS, radiossondas, mapas, iGate e satélites

Arquivos: `pt2vhf/traffic.py`, `sonde_rx.py`, `aprs_map.py`, `aprs_igate.py`, `satellites.py`.

### Escopo declarado 🟢
ADS-B, AIS e telemetria de sondas **não são demodulados do IQ** pelo programa: `traffic.py` só lê arquivos produzidos por decodificadores externos (readsb/dump1090, rtl_ais/AIS-catcher, radiosonde_auto_rx) e "nunca executa software externo". A única exceção é o RS41 (`sonde_rx.py`), que usa o IQ do próprio SDR e binários externos.

### `Track` (entidade comum) 🟢
Valida coordenadas finitas em [−90, 90] × [−180, 180] (senão `ValueError`, e o registro é descartado silenciosamente pelos parsers); timestamp padrão = agora.

### Parsers 🟢
- **ADS-B** (`aircraft.json`): exige `lat`/`lon`; descarta posição com `seen_pos` < 0 ou > 120 s; `hex` obrigatório (≤ 12 caracteres); altitude geométrica, senão barométrica (pés → m); velocidade `gs` (nós → km/h); timestamp = `now − seen_pos`.
- **Radiossondas** (JSON): aceita objeto com `sondes`/`telemetry` (lista ou dict) ou lista; sinônimos de campo (`lat|latitude`, `alt|altitude`, `vel_v|ascent_rate`, `vel_h|speed`, `heading|course`, `id|serial|sonde_id`). Fase: subida se `vel_v` > 0,3 m/s, descida se < −0,3, senão "sem fase". Velocidade horizontal m/s → km/h.
- **AIS** (`AISDecoder`): sentenças `!AIVDM`, `!AIVDO`, `!BSVDM`; checksum NMEA validado se presente; 1–9 fragmentos com chave `(talker, seq, canal, count)` e limite de 100 conjuntos pendentes (estoura → limpa tudo); tipos 1/2/3 (classe A) e 18/19 (classe B) para posição; tipo 5 para nome. Posição em 1/600000 grau; descarta lon ≥ 181° ou lat ≥ 91° (valores "não disponível"); velocidade 1023 e curso 3600 = indisponíveis.
- `load_traffic(path, kind)`: AIS lê só os **últimos 2 MB** do log (descarta a 1ª linha parcial); JSON > **8 MB** é recusado.

### Exportações 🟢
CSV (UTF-8 com BOM), GPX 1.1 (trilha por fonte+id, ordenada por tempo, XML escapado), KML (LineString por fonte+id), mapa HTML Leaflet (até 2000 posições, JSON com `<` escapado; tiles OSM e Leaflet via unpkg exigem Internet).

### RS41 (`sonde_rx.py`) 🟢
- Faixa aceita: **400–406 MHz** (`ValueError` fora). Taxa mínima de IQ: 96 kS/s.
- `ChannelIQ`: desloca a portadora para 0 Hz (`SIGNAL_OFFSET_HZ = 0`) com fase contínua; para taxas múltiplas de 48 kHz usa Butterworth 10ª ordem 19 kHz + decimação com fase persistente; senão `resample_poly` com histórico. Saída **int16 LE intercalado** (escala 30000) a 48 kS/s. Mudança de centro reinicia fase e estado; sonda fora de `fs/2 − 30 kHz` → erro.
- Pipeline externo sem shell: `fsk_demod --cs16 -b -5000 -u 5000 -s --mask 5000 --nsym=300 -p 5 --stats=5 2 48000 4800 - -` → `rs41mod --ptu2 --json --jsnsubfrm1 --softin -i --jsn_cfq <Hz>`. Binários localizados por caminho informado ou `PATH` (`shutil.which`); **sem download automático**.
- Threads: escritor (fila de 12 blocos; cheia → descarta e conta), leitor de JSON, leitores de stderr (guardam estatísticas e erros). Processo encerrado → erro "fsk_demod/rs41mod encerrou com código N".
- `diagnostics()` separa **IQ recebido** de **quadro válido** (`json_frames`, `positions`, `unpositioned_frames`, `invalid_json`).
- Captura de diagnóstico: 1–60 s (padrão 20 s) do IQ reduzido a 48 kS/s.
- **Inconsistência de documentação:** a docstring do módulo ainda cita FI +12 kHz, mas o código centraliza em 0 Hz 🟢.
- Status de homologação: P0 aberto segundo `CLAUDE.md`; o código não comprova decodificação real 🔴.

### Mapa APRS (`aprs_map.py`) 🟢
Histórico em memória: até 150 estações × 40 pontos; ao estourar, remove a estação com posição mais antiga. Exporta HTML Leaflet com JSON escapado (`<`, `>`, `&`) e textos higienizados no navegador.

### iGate APRS-IS somente RX (`aprs_igate.py`) 🟢
- Desativado por padrão; exige indicativo válido (`^[A-Z0-9]{3,7}(-0..15)?$`) e passcode numérico de 1–5 dígitos fornecido pelo operador (nada embutido).
- `gate_line`: descarta linhas com CR/LF/NUL, tráfego de terceiros (`}`), origem inválida, caminho com `TCPIP`, `TCPXX`, `NOGATE`, `RFONLY`, `IGATE`, `GATE` ou `qA*`, e linhas > 512 bytes; acrescenta **`qAO,<indicativo>`** (obrigatório para RX-only, nunca `qAR`).
- Fila de 256; duplicatas em 45 s descartadas; login `user … pass … vers PT2VHF-SDR <versão>`; só envia após `logresp … verified`; reconecta após 5 s (15 s se recusado).
- **Não está ligado à interface atual:** `IGatePanel` existe em `ui/igate_panel.py`, mas a `MainWindow` não o instancia 🟢. Recurso latente.

### Satélites (`satellites.py`) 🟢
- `parse_tles`: aceita formato de 2 ou 3 linhas, ignora `#`, exige mesmo número NORAD nas duas linhas e ≥ 68 caracteres.
- `look_angle`: SGP4 (TEME) → ECEF por rotação GMST (sem nutação/movimento polar), observador WGS-84; retorna azimute, elevação, distância e velocidade radial. Exige data com fuso.
- `receive_doppler_hz = −f·v_r/c` (não relativístico), f ∈ [1 kHz, 10 GHz].
- `next_passes`: amostragem a cada 45 s (mín. 5 s) por até 24 h, máx. 20 000 amostras.
- A `SatellitePanel` é criada (e seu timer de 5 s roda) mas **não é exibida em nenhuma aba**, coerente com "aba Satélites removida, biblioteca orbital preservada" 🟢.

---

## Módulo `ai_audio` — RNNoise, legendas e transcrição

Arquivos: `pt2vhf/neural_audio.py`, `live_caption.py`, `transcribe.py`.

### `NeuralAudioWorker` (RNNoise) 🟢
- Thread `rnnoise-audio`; fila de **8** blocos; cheia → descarta o mais antigo e conta `dropped` (a RF nunca espera a inferência).
- Só aplica em **modos de voz** {NFM, AM, USB, LSB, DSB}; WFM, CW e RAW passam direto. Nunca atua no IQ nem no áudio dos decoders.
- Quadros de 480 amostras a 48 kHz em int16; sobra guardada em `_tail`. Mistura `strength·limpo + (1−strength)·original` (padrão 0,8).
- Falha ao iniciar o backend → evento `neural_error` e passa o áudio original. Falha no processamento → avisa, desliga o backend e segue com áudio original ("nunca silenciar"). Número de amostras retornado diferente do enviado → erro (preserva o relógio).

### `LiveCaptionWorker` 🟢
- Modelos permitidos: `tiny`, `base`, `small`, em `<config>/models/whisper-<tamanho>` (precisa de `model.bin` e `config.json`).
- `install_local_model` só roda por ação explícita do usuário; inferência com `local_files_only=True`, CPU int8, 4 threads.
- Acumula ≥ 4 s (mínimo 2 s); descarta trechos com pico < 0,009; fila de 2 (cheia → substitui o mais antigo); reamostra 48 k → 16 kHz; `vad_filter=True`, `beam_size=1`; idioma `auto` → detecção.
- Resultado: `(timestamp, texto, indicativos, idioma, meta)`, com `meta = (vfo, modo)` lido no momento do envio. Modelo ausente ou import falho encerra o worker.
- `feed` roda na thread DSP; `meta_provider` lê atributos simples da janela (`engine.vfo`, `self.mode`), sem tocar widgets 🟢.

### `Transcriber` 🟢
Fila ilimitada de caminhos WAV (gravações do scanner); modelo padrão `small`, idioma `pt`; erros viram texto vazio.

### Indicativos (`find_callsigns`) 🟢
Regex `\b(?:[A-Z]{1,2}[0-9]|[0-9][A-Z])[0-9]?[A-Z]{1,4}\b` sobre o texto em maiúsculas, sem repetição, exigindo ao menos um dígito.

---

## Módulo `integrations` — web, CAT e OTA

Arquivos: `pt2vhf/webserver.py`, `rigctl.py`, `updater.py`.

### Servidor web (`webserver.py`) 🟢
- Desligado por padrão; porta padrão **8095**; escuta `127.0.0.1` ou `0.0.0.0` (LAN).
- **Somente leitura:** `GET /` (página), `/state` (JSON), `/spectrum` (máx. 1024 pontos por *max-pooling*, 204 sem dados), `/audio` (PCM s16le 16 kHz mono, *chunked*). Qualquer outro caminho → 404; não há rotas de escrita.
- **Autorização:** loopback sempre; sem LAN, só loopback; LAN com `require_key = False` libera qualquer IP privado (10/8, 172.16/12, 192.168/16, link-local, ULA fc00::/7, IPv4 mapeado); caso contrário exige `?key=` (comparação `hmac.compare_digest`) que vira cookie `PT2VHFSDR` HttpOnly SameSite=Strict. Chave aleatória de 24 bytes por execução.
- **Atenção:** o construtor usa `require_key=True` por padrão, mas `Config` traz `web_require_key = False` e a janela repassa o valor da caixa de seleção 🟢 — em LAN, o padrão efetivo depende do estado da UI.
- `AudioHub`: decima 48→16 kHz; fila de 40 por ouvinte, descarta o mais antigo; sem dados por 1 s envia 100 ms de silêncio para manter a conexão.
- Cabeçalhos: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`. HTTP sem TLS (aviso na página).
- `state_fn`/`spectrum_fn` rodam nas threads HTTP e só leem dados prontos (`_web_state` é montado no tick da UI).

### CAT Hamlib (`rigctl.py`) 🟢
- Cliente TCP de `rigctld` (padrão 127.0.0.1:4532, timeout 1,5 s), uma conexão por comando; só `f`, `m`, `F <Hz>` e `M <modo> 0` — **sem PTT**.
- Rejeita comandos com CR/LF ou > 160 caracteres; `RPRT -n` → `RigCtlError`; frequência válida 1 kHz–10 GHz.
- Mapeamento: NFM↔FM (também FMN), CWR→CW; RAW não tem equivalente.
- Na janela, a frequência recebida por CAT precisa estar em 24 kHz–1766 MHz e ser alcançável pela fonte.

### OTA (`updater.py`) 🟢
- Manifesto: `GET https://www.pt2vhf.com/update.php?product=sdr&platform=windows-x64[&kind=installer|portable]`, **sem redirecionamento**, máx. 2 MB, `schema == 1`, `product == "sdr"`, `status == "available"`, versão `vX.Y.Z` maior que a local.
- Tipo de instalação: `source` (Python, nunca se atualiza), `portable` (`portable.flag` ou nome terminando em `-portable`), `installer`.
- Pacote aceito só se URL HTTPS em `www.pt2vhf.com` (sem credenciais, fragmento ou `%`) for `/downloads/sdr-tool/<nome>` sem query ou exatamente `/download.php?product=sdr&file=<nome>`; nome `[A-Za-z0-9_.-]+\.exe`; tamanho inteiro 1 B–600 MB; SHA-256 de 64 hex.
- Download: redirecionamentos permitidos apenas site → `github.com/alexpmr/PT2VHF-SDR-Tool/releases/download/v<versão>/<nome>` → `release-assets.githubusercontent.com` ou `objects.githubusercontent.com`. `Content-Length` divergente, excesso de bytes, tamanho ou hash diferentes → apaga o arquivo e aborta (**falha fechada**).
- Aplicação: só em executável Windows congelado; copia `scripts/apply-update.ps1` para a pasta do pacote e o executa destacado (PowerShell `-ExecutionPolicy Bypass`), passando PID, pacote, destino, executável, modo `Setup`/`Portable` e versão. Resultado lido na próxima abertura de `%TEMP%/PT2VHF-SDR-Tool-update-result.txt` (apagado após leitura).
- `allow_test_host` desliga a validação de host (uso em testes) 🟢.
- Na janela: verificação 12 s após abrir e a cada 6 h; atualização automática adiada enquanto houver gravação, scanner, varredura, replay ou diálogo modal (`operation_busy`); `quit_for_update` força saída após 8 s.
- Estado operacional: `CLAUDE.md` registra OTA **ainda com falha** em campo 🔴 (o código não permite confirmar).

---

## Módulo `ui` — janela principal e painéis

Arquivos: `pt2vhf/ui/*.py` (17 arquivos, ~7 mil linhas) e `pt2vhf/i18n.py`. Análise por responsabilidades; detalhes visuais ficam para o Visor/Design System.

### Estrutura da janela 🟢
Abas principais: **Receptor** (LCD + espectro/waterfall + painel de áudio), **Memórias / Varredura**, **Scanner** (com sub-aba Ocupação 24 h), **Decodificação** (ADS-B, Sondas Meteorológicas [RF RS41 + telemetria externa], AIS, APRS/DTMF/CTCSS), **Ferramentas** (Transcrição, Legendas ao vivo), **Receptores extras**, **Configurações** (Receptor, Modo/Filtro, Display, Geral·Web·Atualizações, CAT·Hamlib).

**Níveis de interface** (`LEVELS`): Essencial (0), Intermediário (1), Avançado (2). Scanner e Decodificação a partir de 1; Receptores extras só no 2; grupos "AGC / Ruído" e "Voltar no tempo" no 2; "Equalizador", "Saída / Gravação", "Assistente" no 1; PPM, bias-T, amostragem direta, tom CW e de-ênfase só no 2. As configurações nunca se perdem ao esconder.

### Laço da interface 🟢
- `QTimer` de **33 ms** (`_tick`): drena `wf_lines` (desenha no máx. 8 por tick), alimenta o scanner, registra ocupação, atualiza S-meter (amostra "fresca" < 2,5 s; senão `S--`), CTCSS, CPU/perdas e processa `engine.events`. Relógio de 1 s.
- Todo resultado de thread (assistente, legendas, transcrição, RS41, iGate, download de modelo) volta à UI como **evento na fila do motor** e é tratado no tick — os widgets só são tocados na thread principal 🟢.

### Sintonia 🟢
- `tune(freq, snap)`: interrompe o scanner se a sintonia não vier dele; arredonda ao passo se `snap`; **limita a 24 kHz–1766 MHz** (também para SoapySDR, cujo hardware pode ir além) 🟢; checa alcance com `check_freq(freq + fs/8)` quando fora da janela atual e mostra aviso não modal.
- VFO A/B com frequência, modo e largura próprios.
- **Waterfall:** clique sintoniza (arredonda ao passo) apenas dentro do IQ adquirido (`_pick_frequency` recusa áreas fora da faixa visível no zoom/pan); duplo clique no waterfall sintoniza e centraliza; duplo clique no espectro reseta zoom; clique dentro do passband do espectro é reservado ao arraste; arrastar o passband inteiro sintoniza, arrastar bordas muda a largura; Ctrl+roda = passos; roda = zoom; arrastar para fora da faixa pede novo centro (`panRequested`) se o deslocamento > 10 % da taxa. O histórico desloca colunas quando o centro muda (estilo KiwiSDR). Linhas com > `MAX_WF_COLS` bins são reduzidas por máximo.
- **Modo AUTO / auto-sintonia** (`_after_select`): 250 ms após selecionar, captura 2,5 s (AUTO) ou 0,6 s (4 s em SSB) de FI e roda `detect_mode`/`fine_tune` fora da UI. Resultado descartado se houve outra seleção (`_sel_gen`) ou o VFO mudou > 1 Hz; AUTO exige confiança ≥ 0,55 e arredonda (10 Hz CW, 1 Hz SSB, 100 Hz demais); auto-sintonia ignora correções < 2 Hz (SSB/CW) ou < 20 Hz.
- **Transmissão vizinha** (◀/▶): `detect_signals` com resolução `clamp(passo, 500, 5000)` e SNR 10 dB; pula sinais a menos de `max(0,6·largura, 1500 Hz)` e bloqueados; sem candidatos, avança 40 % da taxa e tenta de novo (até 20 saltos).

### Outros comportamentos 🟢
- Reconexão automática ao abrir se o receptor estava ligado ao fechar (`rx_was_on`) e a fonte é física; procura o dongle pelo nome salvo, senão pelo índice.
- RS41 só com receptor físico ligado ou arquivo IQ (recusa Simulador), sintoniza na frequência e se registra como `iq_listener`.
- Modo apresentação: tela cheia, opcionalmente mínima (esconde menus, barras, abas, favoritos).
- Fechamento: para RS41, CAT, web, transcrição, legendas e RNNoise; salva geometria (QSettings `PT2VHF/SDRTool`), config, memórias e ocupação; para motor e áudio.
- No Windows cria o mutex `PT2VHF_SDR_Tool_Running` (usado pelo instalador para detectar o programa aberto).

### LCD 🟢
Dígitos de 7 segmentos desenhados; temas Âmbar, Verde, Azul (negativo), Noturno, Branco; escala 50–150 %; edição de frequência por roda/clique por dígito ou digitação em MHz; barra do S-meter com 40 segmentos mapeando −147…−33 dBm (zero sem amostras válidas).

### Idiomas (`i18n.py`) 🟢
7 idiomas (pt, en, es, fr, de, it, zh). Tradução **parcial** por catálogo `WORDS` aplicada a rótulos, botões, grupos, abas e ações, guardando o texto original em propriedades do widget para voltar ao PT-BR.
**Risco:** `apply_level` localiza grupos por `g.title()` em português; com outro idioma ativo, os títulos traduzidos não casam e a visibilidade por nível deixa de ser aplicada a esses grupos 🟡 (inferido da ordem de chamada; não testado).

### Painéis não exibidos 🟢
`IGatePanel` e `TrafficFeedsPanel` existem mas não são instanciados pela janela; `SatellitePanel` é instanciado mas não adicionado a nenhuma aba.

---

## Módulo `app` — inicialização e autoteste

Arquivos: `pt2vhf/app.py`, `__main__.py`, `run_pt2vhf.py`.

- Argumentos: `--debug` (log DEBUG), `--sim` (liga o simulador), `--screenshot PNG` (sem diálogos nem autoconexão; captura após ~11,5 s e sai), `--selftest`. 🟢
- Sem console (`sys.stderr is None`, caso do .exe): log em `<config>/pt2vhf-sdr.log`. 🟢
- **`--selftest`** (código de saída 0/1, log em `%TEMP%/pt2vhf-sdr-selftest.log`) verifica: APRS decodificado do simulador (origem `PY2SIM-9`), assistente detecta AM em 145,650 MHz, abertura da janela, biblioteca RTL-SDR carregada; no .exe Windows também driver Blog, biblioteca padrão, `wdi-simple`, auxiliar de atualização; servidor web responde `/state`; RNNoise processa 2 quadros de 480; faster-whisper + CTranslate2 importáveis; PortAudio (só aviso). 🟢
- O autoteste **não** usa RF real nem valida RS41, ADS-B, AIS ou OTA de ponta a ponta 🟢.

---

## Achados transversais

| # | Achado | Local | Confiança |
|---|--------|-------|-----------|
| 1 | `set_center_freq` tem contratos diferentes: RTL-SDR retorna `False` e avisa; rtl_tcp e SoapySDR lançam `SourceError`. `_retune` só trata o `False` | `sources/*.py`, `engine.py:220` | 🟢 |
| 2 | Sintonia limitada a 24 kHz–1766 MHz na janela, mesmo com SoapySDR que alcança mais | `ui/main_window.py:851` | 🟢 |
| 3 | `Config.save`, `MemoryBank.save` não são atômicos; `MemoryBank.load` não trata JSON corrompido | `config.py`, `memory.py` | 🟢 |
| 4 | Docstring do RS41 cita FI +12 kHz, código usa 0 Hz | `sonde_rx.py:1-8,22` | 🟢 |
| 5 | iGate e painel de feeds de tráfego implementados mas sem acesso pela UI | `ui/igate_panel.py`, `ui/traffic_panel.py:191` | 🟢 |
| 6 | Visibilidade por nível depende de títulos em português | `ui/main_window.py:apply_level` | 🟡 |
| 7 | Padrão de chave da interface web difere entre `WebServer` (True) e `Config` (False) | `webserver.py`, `config.py` | 🟢 |
| 8 | Timeshift quantiza em 8 bits, perdendo faixa dinâmica de fontes melhores que o RTL-SDR | `timeshift.py` | 🟡 |
| 9 | Offset do S-meter (−45 dB) é nominal; dBm absoluto sem calibração | `dsp/demod.py:dbfs_to_s_units` | 🟢 nominal / 🔴 precisão |
| 10 | RS41, OTA em campo, RNNoise/Whisper com RF real: implementados, não homologados | vários | 🔴 |
