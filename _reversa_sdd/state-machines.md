# Máquinas de estado — PT2VHF SDR Tool

Extraídas pelo Detetive a partir do código da branch `claude/project-thread-hzahgn` (base PR #32, v0.13.3).
Escala: 🟢 confirmado no código · 🟡 inferido · 🔴 lacuna.

## 1. Fonte RTL-SDR: saúde da recepção 🟢
`pt2vhf/sources/rtlsdr_source.py:183,478-503` (`status`: ok | recovering | failed)

```mermaid
stateDiagram-v2
    [*] --> ok: abertura do dongle
    ok --> recovering: comando travado > CMD_TIMEOUT_S ou sem blocos > STALL_S
    recovering --> recovering: nova falha (tentativa n de MAX_RECOVER)
    recovering --> ok: bloco recebido há menos de 0,5 s
    recovering --> failed: falhas > MAX_RECOVER
    failed --> [*]: vigia encerra e pede reconectar o dongle e clicar Ligar
```

Regras:
- O vigia roda a cada 0,25 s. A recuperação cancela a leitura antiga em thread separada e reabre o dispositivo.
- Ao voltar a `ok`, o contador de falhas zera e a mensagem "Recepção restabelecida." é emitida.
- 🟡 rtl_tcp e SoapySDR não têm essa máquina; erros sobem como `SourceError`.

## 2. Scanner espectral 🟢
`pt2vhf/scanner.py:145-360` (`state`: idle | settle | dwell | priority | listen)

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> settle: start() sintoniza o primeiro segmento
    settle --> dwell: settle_lines descartadas
    settle --> priority: settle após salto ao canal prioritário
    dwell --> settle: fim do dwell, próximo segmento
    dwell --> priority: priority_interval_s vencido
    dwell --> listen: acerto acima de piso + SNR, fora de lockout e cooldown
    priority --> listen: canal prioritário ativo
    priority --> settle: prioritário inativo, volta ao segmento
    listen --> settle: sem atividade por resume_s ou max_listen_s excedido
    listen --> dwell: retomada num único segmento já centrado
    settle --> idle: stop()
    dwell --> idle: stop()
    listen --> idle: stop()
```

Regras:
- Em `listen`, o limiar de atividade é `piso + 0,7 × snr_db` (histerese implícita).
- Ao sair de `listen`, a frequência entra em `_cooldown`, evitando parar de novo no mesmo canal logo em seguida.
- Lockout usa tolerância por frequência arredondada.

## 3. Squelch 🟢
`pt2vhf/dsp/demod.py:146-167`

```mermaid
stateDiagram-v2
    [*] --> aberto: threshold padrão -150 dB
    aberto --> cauda: nível < threshold - histerese (3 dB)
    cauda --> aberto: nível >= threshold
    cauda --> fechado: cauda de 0,25 s esgotada
    fechado --> aberto: nível >= threshold
```

## 4. Gravação por atividade (ActivityRecorder) 🟢
`pt2vhf/audio.py:144-240`

```mermaid
stateDiagram-v2
    [*] --> ocioso
    ocioso --> ocioso: squelch fechado, guarda pré-gravação (0,5 s)
    ocioso --> gravando: squelch abre, cria WAV e despeja a pré-gravação
    gravando --> gravando: áudio aberto ou cauda < tail_s (1,5 s)
    gravando --> finalizando: fechado >= tail_s ou duração >= max_s (300 s) ou frequência mudou
    finalizando --> ocioso: duração >= min_s (1 s), emite evento
    finalizando --> descartado: duração < min_s, apaga o arquivo
    descartado --> ocioso
```

Variante `single_file` (VOX de sessão): todas as transmissões vão para um único arquivo `_VOX`; trechos curtos não geram evento, mas o arquivo não é apagado.

## 5. Timeshift (voltar no tempo) 🟢
`pt2vhf/engine.py:236-269,360-367`

```mermaid
stateDiagram-v2
    [*] --> desligado: timeshift_seconds = 0
    [*] --> ao_vivo: buffer criado ao abrir a fonte (padrão 20 s)
    ao_vivo --> replay: start_replay(segundos) emite "replay"
    replay --> ao_vivo: stop_replay() emite "replay_end"
    replay --> ao_vivo: leitura alcança o presente
    ao_vivo --> desligado: set_timeshift(0)
    replay --> ao_vivo: set_timeshift recria o buffer
```

## 6. Saída de áudio (priming) 🟢
`pt2vhf/audio.py:36-105`

```mermaid
stateDiagram-v2
    [*] --> enchendo: start()
    enchendo --> tocando: fila >= alvo de latência (0,15 s)
    tocando --> enchendo: underrun (contador underruns++)
    enchendo --> enchendo: entrega silêncio até encher
```

## 7. Atualização OTA (UpdateController) 🟢
`pt2vhf/ui/assist_panels.py:196-330`, `pt2vhf/updater.py`

```mermaid
stateDiagram-v2
    [*] --> verificando: início (instalador/portátil) ou clique manual
    verificando --> sem_novidade: manifesto sem versão mais nova
    verificando --> erro: manifesto inválido ou rede
    verificando --> manual: install_kind = source
    verificando --> indisponivel: versão nova sem pacote válido (URL, tamanho, SHA-256)
    verificando --> disponivel: pacote válido para o tipo de instalação
    disponivel --> adiado: operation_busy() (gravação, scanner, replay)
    adiado --> disponivel: nova tentativa a cada 60 s
    disponivel --> perguntando: maybe_prompt (respeita soneca e diálogos modais)
    perguntando --> baixando: Atualizar agora
    perguntando --> soneca: Depois
    baixando --> aplicando: SHA-256 e tamanho conferem
    baixando --> falhou: verificação falha, registra update_failed
    aplicando --> [*]: auxiliar PowerShell substitui e reinicia
    falhou --> disponivel: após RETRY_FAIL_S
```

🔴 O fluxo ponta a ponta no Windows real não está homologado (P0 do BACKLOG).

## 8. Receptor RS41 🟢/🔴
`pt2vhf/sonde_rx.py:113-330`

```mermaid
stateDiagram-v2
    [*] --> parado
    parado --> sem_binarios: fsk_demod ou rs41mod não encontrados
    parado --> aguardando: start() inicia pipes (IQ 48 kS/s, banda base 0 Hz)
    aguardando --> decodificando: rs41mod emite quadro JSON válido
    aguardando --> erro: falha de pipe ou stderr com erro
    decodificando --> aguardando: sem quadros por um tempo (🟡)
    aguardando --> capturando: start_capture(path, 20 s)
    capturando --> aguardando: captura fechada
    erro --> parado: stop()
    decodificando --> parado: stop()
```

🔴 Nunca demonstrado com RF real (serial, posição e altitude no mapa).

## 9. iGate APRS-IS (código órfão) 🟡
`pt2vhf/aprs_igate.py:71-170`. A UI foi removida na v0.10.0; a máquina existe só no código.

```mermaid
stateDiagram-v2
    [*] --> desligado
    desligado --> conectando: start() com indicativo e passcode válidos
    conectando --> verificado: logresp verified em até 12 s
    conectando --> recusado: login não verificado
    conectando --> indisponivel: erro de socket
    recusado --> conectando: espera 15 s
    verificado --> indisponivel: queda de conexão
    indisponivel --> conectando: espera 5 s
    verificado --> desligado: stop()
    recusado --> desligado: stop()
```

## Lacunas
- 🔴 Comportamento do watchdog com rtl_tcp/SoapySDR sob falha real.
- 🟡 Estado do decodificador APRS/AFSK não é uma máquina explícita (fluxo contínuo de bits).
- 🟡 Estados de gravação manual de áudio/IQ são booleanos (`recording_audio`, `recording_iq`) sem máquina formal.
